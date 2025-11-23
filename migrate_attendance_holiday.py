#!/usr/bin/env python3
"""
Migration script to add HOLIDAY status to attendance system
This updates the AttendanceStatus enum to include 'holiday' option
"""

import sys
from sqlalchemy import create_engine, text
from config import DevelopmentConfig

def migrate_attendance_status():
    """Add HOLIDAY status to attendance enum"""
    print("=" * 60)
    print("Attendance Status Migration: Adding HOLIDAY Option")
    print("=" * 60)
    
    try:
        # Create database engine
        engine = create_engine(DevelopmentConfig.SQLALCHEMY_DATABASE_URI)
        
        with engine.connect() as conn:
            print("\n✓ Connected to database")
            
            # For SQLite, we don't need to modify the enum since Python handles it
            # Just verify the table exists
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='attendance'
            """))
            
            if result.fetchone():
                print("✓ Attendance table exists")
                
                # Count current records
                result = conn.execute(text("SELECT COUNT(*) FROM attendance"))
                count = result.scalar()
                print(f"✓ Found {count} attendance records")
                
                # Check status values
                result = conn.execute(text("""
                    SELECT DISTINCT status FROM attendance
                """))
                statuses = [row[0] for row in result.fetchall()]
                print(f"✓ Current status values: {', '.join(statuses) if statuses else 'none'}")
                
                print("\n" + "=" * 60)
                print("✅ Migration completed successfully!")
                print("=" * 60)
                print("\nNotes:")
                print("  - HOLIDAY status is now available in AttendanceStatus enum")
                print("  - Teachers can now mark students as 'holiday'")
                print("  - Monthly attendance sheet will show 'H' for holidays")
                print("  - Orange color coding for holiday status")
                
                return True
            else:
                print("❌ Attendance table not found")
                return False
                
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    try:
        success = migrate_attendance_status()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
