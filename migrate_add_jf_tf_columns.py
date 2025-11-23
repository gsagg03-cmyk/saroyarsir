#!/usr/bin/env python3
"""
Migration script to add jf_amount and tf_amount columns to fees table
This allows tracking JF (জানুয়ারি ফি) and TF (টিউশন ফি) separately for each month
"""

import sys
import os
from sqlalchemy import create_engine, text, inspect
from config import DevelopmentConfig

def add_jf_tf_columns():
    """Add jf_amount and tf_amount columns to fees table"""
    print("Adding JF and TF columns to fees table...")
    
    try:
        # Create database engine using DevelopmentConfig
        engine = create_engine(DevelopmentConfig.SQLALCHEMY_DATABASE_URI)
        
        with engine.connect() as conn:
            # Get current columns
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('fees')]
            print(f"Current columns: {columns}")
            
            # Add jf_amount if not exists
            if 'jf_amount' not in columns:
                print("Adding jf_amount column to fees table...")
                conn.execute(text("""
                    ALTER TABLE fees
                    ADD COLUMN jf_amount NUMERIC(10, 2) DEFAULT 0.00
                """))
                conn.commit()
                print("✅ Added jf_amount column")
            else:
                print("⚠️  jf_amount column already exists")
            
            # Add tf_amount if not exists
            if 'tf_amount' not in columns:
                print("Adding tf_amount column to fees table...")
                conn.execute(text("""
                    ALTER TABLE fees
                    ADD COLUMN tf_amount NUMERIC(10, 2) DEFAULT 0.00
                """))
                conn.commit()
                print("✅ Added tf_amount column")
            else:
                print("⚠️  tf_amount column already exists")
            
            # Migrate existing data: split amount into jf_amount and tf_amount
            print("\nMigrating existing fee data...")
            
            # For backward compatibility, we'll set jf_amount = amount and tf_amount = 0
            # This ensures existing fees are preserved
            result = conn.execute(text("""
                UPDATE fees 
                SET jf_amount = amount, tf_amount = 0.00
                WHERE jf_amount = 0 AND tf_amount = 0 AND amount > 0
            """))
            conn.commit()
            
            rows_updated = result.rowcount
            print(f"✅ Migrated {rows_updated} existing fee records")
            
        # Verify changes
        inspector = inspect(engine)
        columns_after = [col['name'] for col in inspector.get_columns('fees')]
        
        if 'jf_amount' in columns_after and 'tf_amount' in columns_after:
            print("\n✅ SUCCESS: Fee table now has JF and TF columns")
            print(f"   - jf_amount: for জানুয়ারি ফি (JF)")
            print(f"   - tf_amount: for টিউশন ফি (TF)")
            return True
        else:
            print("\n❌ FAILED: Columns were not added successfully")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Fee Table Migration: Adding JF and TF Columns")
    print("=" * 60)
    print()
    
    try:
        success = add_jf_tf_columns()
        
        if success:
            print("\n" + "=" * 60)
            print("✅ Migration completed successfully!")
            print("=" * 60)
            sys.exit(0)
        else:
            print("\n" + "=" * 60)
            print("❌ Migration failed!")
            print("=" * 60)
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
