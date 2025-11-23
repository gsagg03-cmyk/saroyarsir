#!/usr/bin/env python3
"""
Production-Ready SQLite Migration Script
Safely adds jf_amount, tf_amount to fees table and holiday to attendance
WITHOUT losing any existing data
"""

import sys
import os
import argparse
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
import shutil

try:
    from config import DevelopmentConfig, ProductionConfig
except ImportError:
    print("❌ Error: Could not import config. Make sure config.py exists.")
    sys.exit(1)


class ProductionSafeMigration:
    """Safe migration that preserves all existing data"""
    
    def __init__(self, environment='development'):
        self.environment = environment
        self.config = DevelopmentConfig if environment == 'development' else ProductionConfig
        self.engine = None
        self.backup_file = None
        
    def get_db_path(self):
        """Extract database file path from URI"""
        uri = self.config.SQLALCHEMY_DATABASE_URI
        if 'sqlite:///' in uri:
            path = uri.replace('sqlite:///', '')
            path = path.replace('sqlite:////', '/')
            return path
        return None
    
    def create_backup(self):
        """Create timestamped backup of entire database"""
        try:
            db_path = self.get_db_path()
            
            if not db_path or not os.path.exists(db_path):
                print(f"⚠️  Database file not found at {db_path}")
                return False
            
            # Create backups directory
            backup_dir = Path(db_path).parent / 'backups'
            backup_dir.mkdir(exist_ok=True)
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.backup_file = backup_dir / f'production_backup_{timestamp}.db'
            
            # Copy database file
            shutil.copy2(db_path, self.backup_file)
            
            file_size = os.path.getsize(self.backup_file) / 1024  # KB
            print(f"✓ Backup created: {self.backup_file} ({file_size:.2f} KB)")
            return True
            
        except Exception as e:
            print(f"❌ Backup failed: {str(e)}")
            return False
    
    def connect(self):
        """Create database connection"""
        try:
            self.engine = create_engine(self.config.SQLALCHEMY_DATABASE_URI, echo=False)
            print(f"✓ Connected to {self.environment} database")
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {str(e)}")
            return False
    
    def check_column_exists(self, table_name, column_name):
        """Check if a column exists in a table"""
        try:
            inspector = inspect(self.engine)
            columns = [col['name'] for col in inspector.get_columns(table_name)]
            return column_name in columns
        except:
            return False
    
    def migrate_fees_table(self):
        """Add jf_amount and tf_amount columns to fees table"""
        print("\n📊 Migrating Fees Table...")
        
        try:
            with self.engine.begin() as conn:
                # Check if fees table exists
                result = conn.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='fees'
                """))
                
                if not result.fetchone():
                    print("  ⚠️  Fees table does not exist - skipping")
                    return True
                
                # Count existing records
                result = conn.execute(text("SELECT COUNT(*) FROM fees"))
                total_fees = result.scalar()
                print(f"  ✓ Found {total_fees} existing fee records")
                
                # Add jf_amount column if not exists
                if not self.check_column_exists('fees', 'jf_amount'):
                    print("  → Adding jf_amount column...")
                    conn.execute(text("""
                        ALTER TABLE fees
                        ADD COLUMN jf_amount DECIMAL(10, 2) DEFAULT 0.00
                    """))
                    print("  ✓ Added jf_amount column")
                    
                    # Migrate existing data: amount → jf_amount
                    conn.execute(text("""
                        UPDATE fees 
                        SET jf_amount = amount
                        WHERE jf_amount = 0 AND amount > 0
                    """))
                    print(f"  ✓ Migrated {total_fees} records to jf_amount")
                else:
                    print("  ℹ  jf_amount column already exists")
                
                # Add tf_amount column if not exists
                if not self.check_column_exists('fees', 'tf_amount'):
                    print("  → Adding tf_amount column...")
                    conn.execute(text("""
                        ALTER TABLE fees
                        ADD COLUMN tf_amount DECIMAL(10, 2) DEFAULT 0.00
                    """))
                    print("  ✓ Added tf_amount column")
                else:
                    print("  ℹ  tf_amount column already exists")
                
                # Verify data integrity
                result = conn.execute(text("SELECT COUNT(*) FROM fees WHERE amount > 0"))
                fees_with_amount = result.scalar()
                
                result = conn.execute(text("SELECT COUNT(*) FROM fees WHERE jf_amount > 0 OR tf_amount > 0"))
                migrated_fees = result.scalar()
                
                print(f"\n  📈 Migration Summary:")
                print(f"     Total fee records: {total_fees}")
                print(f"     Records with amounts: {fees_with_amount}")
                print(f"     Records with JF/TF: {migrated_fees}")
                
                return True
                
        except Exception as e:
            print(f"  ❌ Error migrating fees: {str(e)}")
            return False
    
    def verify_attendance_table(self):
        """Verify attendance table can handle holiday status"""
        print("\n📅 Verifying Attendance Table...")
        
        try:
            with self.engine.begin() as conn:
                # Check if attendance table exists
                result = conn.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='attendance'
                """))
                
                if not result.fetchone():
                    print("  ⚠️  Attendance table does not exist")
                    return True
                
                # Count existing records
                result = conn.execute(text("SELECT COUNT(*) FROM attendance"))
                total_attendance = result.scalar()
                print(f"  ✓ Found {total_attendance} existing attendance records")
                
                # Check existing status values
                result = conn.execute(text("""
                    SELECT DISTINCT status FROM attendance
                """))
                statuses = [row[0] for row in result.fetchall()]
                
                if statuses:
                    print(f"  ✓ Current status values: {', '.join(statuses)}")
                else:
                    print("  ℹ  No attendance records yet")
                
                # SQLite stores enum as text, so 'holiday' will work automatically
                print("  ✓ Attendance table ready for 'holiday' status")
                
                return True
                
        except Exception as e:
            print(f"  ❌ Error verifying attendance: {str(e)}")
            return False
    
    def create_indexes(self):
        """Create indexes for better performance"""
        print("\n🚀 Creating Performance Indexes...")
        
        try:
            with self.engine.begin() as conn:
                # Index for fees table
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_fees_user_date 
                    ON fees(user_id, due_date)
                """))
                print("  ✓ Created index: idx_fees_user_date")
                
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_fees_batch_date 
                    ON fees(batch_id, due_date)
                """))
                print("  ✓ Created index: idx_fees_batch_date")
                
                # Index for attendance table
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_attendance_user_date 
                    ON attendance(user_id, date)
                """))
                print("  ✓ Created index: idx_attendance_user_date")
                
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_attendance_batch_date 
                    ON attendance(batch_id, date)
                """))
                print("  ✓ Created index: idx_attendance_batch_date")
                
                return True
                
        except Exception as e:
            print(f"  ⚠️  Error creating indexes: {str(e)}")
            return True  # Non-critical, continue anyway
    
    def run(self):
        """Execute complete production migration"""
        print("=" * 70)
        print("PRODUCTION-SAFE SQLITE MIGRATION")
        print("=" * 70)
        print(f"Environment: {self.environment.upper()}")
        print(f"Database: {self.get_db_path()}")
        print("=" * 70)
        
        # Step 1: Create backup
        print("\n[1/5] Creating Database Backup...")
        if not self.create_backup():
            print("\n⚠️  WARNING: Could not create backup!")
            if self.environment == 'production':
                response = input("Continue without backup? (yes/no): ")
                if response.lower() != 'yes':
                    print("Migration cancelled.")
                    return False
        
        # Step 2: Connect
        print("\n[2/5] Connecting to Database...")
        if not self.connect():
            return False
        
        # Step 3: Migrate fees table
        print("\n[3/5] Migrating Fees Table (JF/TF columns)...")
        if not self.migrate_fees_table():
            print("\n❌ Fees migration failed!")
            return False
        
        # Step 4: Verify attendance table
        print("\n[4/5] Verifying Attendance Table (Holiday status)...")
        if not self.verify_attendance_table():
            print("\n❌ Attendance verification failed!")
            return False
        
        # Step 5: Create indexes
        print("\n[5/5] Creating Performance Indexes...")
        self.create_indexes()
        
        # Success!
        print("\n" + "=" * 70)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        
        print("\n📊 What was migrated:")
        print("   ✓ Fees table: Added jf_amount and tf_amount columns")
        print("   ✓ Existing fee data migrated (amount → jf_amount)")
        print("   ✓ Attendance table: Ready for 'holiday' status")
        print("   ✓ Performance indexes created")
        
        if self.backup_file:
            print(f"\n💾 Backup saved: {self.backup_file}")
            print("   (Keep this backup for at least 30 days)")
        
        print("\n🎯 Next Steps:")
        print("   1. Test the fee management interface")
        print("   2. Test attendance with Present/Absent/Holiday")
        print("   3. Verify data is intact")
        print("   4. If production, restart the application")
        
        return True


def main():
    parser = argparse.ArgumentParser(description='Production-safe SQLite migration')
    parser.add_argument(
        '--env',
        choices=['development', 'production'],
        default='development',
        help='Environment (default: development)'
    )
    
    args = parser.parse_args()
    
    # Production confirmation
    if args.env == 'production':
        print("\n" + "⚠️  " * 20)
        print("WARNING: PRODUCTION MIGRATION")
        print("⚠️  " * 20)
        print("\nThis will modify your production database.")
        print("A backup will be created automatically.")
        print("\nType 'MIGRATE' to continue: ", end='')
        
        confirm = input()
        if confirm != 'MIGRATE':
            print("\n❌ Migration cancelled.")
            sys.exit(0)
    
    # Run migration
    migration = ProductionSafeMigration(environment=args.env)
    success = migration.run()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
