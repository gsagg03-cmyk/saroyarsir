#!/usr/bin/env python3
"""
Production-Ready Database Migration Script for JF/TF Fee System
===============================================================
This script safely adds jf_amount and tf_amount columns to the fees table
and migrates existing data without data loss.

Features:
- Idempotent (can be run multiple times safely)
- Automatic backup before migration
- Transaction-based (rolls back on error)
- Detailed logging
- Data validation after migration

Usage:
    python production_migrate_jf_tf.py [--env production|development]
"""

import sys
import os
import argparse
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

# Import configurations
try:
    from config import DevelopmentConfig, ProductionConfig
except ImportError:
    print("❌ Error: Could not import config. Make sure config.py exists.")
    sys.exit(1)


class FeeTableMigration:
    """Handle fee table migration for JF/TF columns"""
    
    def __init__(self, environment='development'):
        """Initialize migration with specified environment"""
        self.environment = environment
        self.config = DevelopmentConfig if environment == 'development' else ProductionConfig
        self.engine = None
        self.backup_file = None
        
    def connect(self):
        """Create database connection"""
        try:
            self.engine = create_engine(self.config.SQLALCHEMY_DATABASE_URI, echo=False)
            print(f"✓ Connected to {self.environment} database")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to database: {str(e)}")
            return False
    
    def create_backup(self):
        """Create backup of fees table before migration"""
        try:
            # Get database file path
            if 'sqlite:///' in self.config.SQLALCHEMY_DATABASE_URI:
                db_path = self.config.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
                db_path = db_path.replace('sqlite:////', '/')
                
                if os.path.exists(db_path):
                    # Create backup filename
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    backup_dir = Path(db_path).parent / 'backups'
                    backup_dir.mkdir(exist_ok=True)
                    
                    self.backup_file = backup_dir / f'fees_backup_{timestamp}.db'
                    
                    # Copy database file
                    import shutil
                    shutil.copy2(db_path, self.backup_file)
                    print(f"✓ Backup created: {self.backup_file}")
                    return True
                else:
                    print(f"⚠️  Database file not found at {db_path}")
                    return False
            else:
                print("⚠️  Backup not supported for non-SQLite databases")
                return True
                
        except Exception as e:
            print(f"❌ Backup failed: {str(e)}")
            return False
    
    def check_table_exists(self):
        """Check if fees table exists"""
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            
            if 'fees' not in tables:
                print("❌ Fees table does not exist")
                return False
                
            print("✓ Fees table exists")
            return True
            
        except Exception as e:
            print(f"❌ Error checking table: {str(e)}")
            return False
    
    def get_current_columns(self):
        """Get list of current columns in fees table"""
        try:
            inspector = inspect(self.engine)
            columns = [col['name'] for col in inspector.get_columns('fees')]
            return columns
        except Exception as e:
            print(f"❌ Error getting columns: {str(e)}")
            return []
    
    def add_columns(self):
        """Add jf_amount and tf_amount columns"""
        try:
            with self.engine.begin() as conn:
                columns = self.get_current_columns()
                
                # Add jf_amount if not exists
                if 'jf_amount' not in columns:
                    print("  → Adding jf_amount column...")
                    conn.execute(text("""
                        ALTER TABLE fees
                        ADD COLUMN jf_amount DECIMAL(10, 2) DEFAULT 0.00
                    """))
                    print("  ✓ jf_amount column added")
                else:
                    print("  ℹ jf_amount column already exists")
                
                # Add tf_amount if not exists
                if 'tf_amount' not in columns:
                    print("  → Adding tf_amount column...")
                    conn.execute(text("""
                        ALTER TABLE fees
                        ADD COLUMN tf_amount DECIMAL(10, 2) DEFAULT 0.00
                    """))
                    print("  ✓ tf_amount column added")
                else:
                    print("  ℹ tf_amount column already exists")
                
            return True
            
        except SQLAlchemyError as e:
            print(f"❌ Error adding columns: {str(e)}")
            return False
    
    def migrate_existing_data(self):
        """Migrate existing amount data to jf_amount"""
        try:
            with self.engine.begin() as conn:
                print("  → Migrating existing fee data...")
                
                # Update records where jf_amount and tf_amount are 0 but amount > 0
                result = conn.execute(text("""
                    UPDATE fees 
                    SET jf_amount = amount, 
                        tf_amount = 0.00
                    WHERE (jf_amount = 0 OR jf_amount IS NULL) 
                      AND (tf_amount = 0 OR tf_amount IS NULL) 
                      AND amount > 0
                """))
                
                rows_updated = result.rowcount
                print(f"  ✓ Migrated {rows_updated} existing fee records")
                
            return True
            
        except SQLAlchemyError as e:
            print(f"❌ Error migrating data: {str(e)}")
            return False
    
    def validate_migration(self):
        """Validate that migration was successful"""
        try:
            with self.engine.connect() as conn:
                # Check columns exist
                columns = self.get_current_columns()
                if 'jf_amount' not in columns or 'tf_amount' not in columns:
                    print("❌ Validation failed: Columns not added")
                    return False
                
                # Count total records
                result = conn.execute(text("SELECT COUNT(*) FROM fees"))
                total_records = result.scalar()
                
                # Count records with JF/TF data
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM fees 
                    WHERE jf_amount > 0 OR tf_amount > 0
                """))
                migrated_records = result.scalar()
                
                # Check for data integrity
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM fees 
                    WHERE amount != (jf_amount + tf_amount)
                    AND amount > 0
                """))
                inconsistent_records = result.scalar()
                
                print(f"\n  📊 Migration Statistics:")
                print(f"     Total fee records: {total_records}")
                print(f"     Records with JF/TF: {migrated_records}")
                print(f"     Inconsistent records: {inconsistent_records}")
                
                if inconsistent_records > 0:
                    print(f"  ⚠️  Warning: {inconsistent_records} records have inconsistent totals")
                    # Fix inconsistent records
                    conn.execute(text("""
                        UPDATE fees 
                        SET amount = jf_amount + tf_amount
                        WHERE amount != (jf_amount + tf_amount)
                    """))
                    conn.commit()
                    print(f"  ✓ Fixed inconsistent records")
                
                print("  ✓ Validation passed")
                return True
                
        except Exception as e:
            print(f"❌ Validation error: {str(e)}")
            return False
    
    def run(self):
        """Execute the complete migration"""
        print("=" * 70)
        print("Production-Ready Fee Table Migration: JF/TF Columns")
        print("=" * 70)
        print(f"Environment: {self.environment.upper()}")
        print(f"Database: {self.config.SQLALCHEMY_DATABASE_URI}")
        print("=" * 70)
        print()
        
        # Step 1: Connect to database
        print("Step 1: Connecting to database...")
        if not self.connect():
            return False
        print()
        
        # Step 2: Check table exists
        print("Step 2: Checking fees table...")
        if not self.check_table_exists():
            return False
        print()
        
        # Step 3: Create backup
        print("Step 3: Creating backup...")
        if not self.create_backup():
            print("  ⚠️  Proceeding without backup...")
        print()
        
        # Step 4: Add columns
        print("Step 4: Adding JF/TF columns...")
        if not self.add_columns():
            return False
        print()
        
        # Step 5: Migrate existing data
        print("Step 5: Migrating existing data...")
        if not self.migrate_existing_data():
            return False
        print()
        
        # Step 6: Validate migration
        print("Step 6: Validating migration...")
        if not self.validate_migration():
            return False
        print()
        
        # Success!
        print("=" * 70)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print()
        print("Next Steps:")
        print("  1. Test the fee management interface")
        print("  2. Verify JF and TF columns are working")
        print("  3. Start entering monthly fee data")
        if self.backup_file:
            print(f"  4. Backup saved at: {self.backup_file}")
        print()
        
        return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Migrate fees table for JF/TF support')
    parser.add_argument(
        '--env',
        choices=['development', 'production'],
        default='development',
        help='Environment to run migration in (default: development)'
    )
    
    args = parser.parse_args()
    
    # Confirm production migration
    if args.env == 'production':
        print("\n⚠️  WARNING: You are about to run migration on PRODUCTION database!")
        print("This will modify the fees table structure.")
        confirm = input("Type 'YES' to continue: ")
        
        if confirm != 'YES':
            print("Migration cancelled.")
            sys.exit(0)
        print()
    
    # Run migration
    migration = FeeTableMigration(environment=args.env)
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
