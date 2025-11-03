#!/usr/bin/env python3
"""
Database Migration: Remove UNIQUE constraint from users.phoneNumber
This allows multiple students (siblings) to share the same phone number.

CRITICAL: This migration is required for multi-student account feature.
"""

import sys
from app import create_app
from models import db
from sqlalchemy import text

def migrate_remove_phone_unique_constraint():
    """Remove UNIQUE constraint from phoneNumber field"""
    app = create_app()
    
    with app.app_context():
        print("=" * 70)
        print("DATABASE MIGRATION: Remove UNIQUE constraint from phoneNumber")
        print("=" * 70)
        
        # Check database type
        db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        is_sqlite = 'sqlite' in db_url.lower()
        is_mysql = 'mysql' in db_url.lower()
        
        print(f"\n📊 Database Type: {'SQLite' if is_sqlite else 'MySQL' if is_mysql else 'Unknown'}")
        print(f"📍 Database URL: {db_url[:50]}...")
        
        try:
            if is_sqlite:
                print("\n⚠️  SQLite detected - Requires table recreation")
                print("   SQLite doesn't support ALTER TABLE DROP CONSTRAINT")
                print("   Will recreate the users table without the constraint")
                
                # For SQLite, we need to recreate the table
                print("\n🔄 Step 1: Creating backup of users table...")
                db.session.execute(text("""
                    CREATE TABLE users_backup AS SELECT * FROM users
                """))
                db.session.commit()
                print("   ✅ Backup created: users_backup")
                
                print("\n🔄 Step 2: Dropping original users table...")
                db.session.execute(text("DROP TABLE users"))
                db.session.commit()
                print("   ✅ Original table dropped")
                
                print("\n🔄 Step 3: Recreating users table without UNIQUE constraint...")
                # Drop all tables and recreate (this will use the updated model)
                db.drop_all()
                db.create_all()
                print("   ✅ Tables recreated with new schema")
                
                print("\n🔄 Step 4: Restoring data from backup...")
                db.session.execute(text("""
                    INSERT INTO users 
                    SELECT * FROM users_backup
                """))
                db.session.commit()
                print("   ✅ Data restored")
                
                print("\n🔄 Step 5: Dropping backup table...")
                db.session.execute(text("DROP TABLE users_backup"))
                db.session.commit()
                print("   ✅ Backup table dropped")
                
            elif is_mysql:
                print("\n🔄 MySQL Migration...")
                
                # Check if constraint exists
                print("\n🔍 Checking for existing UNIQUE constraint...")
                result = db.session.execute(text("""
                    SELECT CONSTRAINT_NAME 
                    FROM information_schema.TABLE_CONSTRAINTS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'users' 
                    AND CONSTRAINT_TYPE = 'UNIQUE'
                    AND CONSTRAINT_NAME LIKE '%phoneNumber%'
                """))
                
                constraints = [row[0] for row in result]
                
                if constraints:
                    for constraint_name in constraints:
                        print(f"   Found constraint: {constraint_name}")
                        print(f"\n🔄 Dropping UNIQUE constraint: {constraint_name}...")
                        db.session.execute(text(f"""
                            ALTER TABLE users DROP INDEX `{constraint_name}`
                        """))
                        db.session.commit()
                        print(f"   ✅ Constraint dropped: {constraint_name}")
                else:
                    print("   ℹ️  No UNIQUE constraint found on phoneNumber")
                
                # Ensure index exists (without UNIQUE)
                print("\n🔄 Creating non-unique index on phoneNumber...")
                try:
                    db.session.execute(text("""
                        CREATE INDEX idx_users_phoneNumber ON users (phoneNumber)
                    """))
                    db.session.commit()
                    print("   ✅ Index created")
                except Exception as e:
                    if 'Duplicate key name' in str(e) or 'already exists' in str(e):
                        print("   ℹ️  Index already exists")
                    else:
                        raise
            
            else:
                print("\n❌ Unsupported database type")
                print("   Please manually remove the UNIQUE constraint from phoneNumber")
                return False
            
            # Verify the change
            print("\n" + "=" * 70)
            print("✅ MIGRATION COMPLETED SUCCESSFULLY")
            print("=" * 70)
            
            # Test: Try to create two users with same phone
            print("\n🧪 Testing: Creating two users with same phone number...")
            from models import User, UserRole
            from werkzeug.security import generate_password_hash
            
            test_phone = '01999999999'
            
            # Clean up any existing test users
            User.query.filter_by(phoneNumber=test_phone).delete()
            db.session.commit()
            
            # Create first student
            student1 = User(
                phoneNumber=test_phone,
                password_hash=generate_password_hash('student123'),
                first_name='Test1',
                last_name='Student1',
                role=UserRole.STUDENT,
                is_active=True
            )
            db.session.add(student1)
            db.session.commit()
            print(f"   ✅ Created student 1: Test1 Student1 ({test_phone})")
            
            # Create second student with SAME phone
            student2 = User(
                phoneNumber=test_phone,
                password_hash=generate_password_hash('student123'),
                first_name='Test2',
                last_name='Student2',
                role=UserRole.STUDENT,
                is_active=True
            )
            db.session.add(student2)
            db.session.commit()
            print(f"   ✅ Created student 2: Test2 Student2 ({test_phone})")
            
            # Verify both exist
            test_students = User.query.filter_by(phoneNumber=test_phone).all()
            print(f"\n   ✅ Verification: Found {len(test_students)} students with phone {test_phone}")
            
            # Clean up test data
            User.query.filter_by(phoneNumber=test_phone).delete()
            db.session.commit()
            print(f"   🗑️  Test users deleted")
            
            print("\n" + "=" * 70)
            print("🎉 MULTI-STUDENT FEATURE IS NOW ENABLED!")
            print("=" * 70)
            print("\n✅ You can now:")
            print("   • Create multiple students with the same phone number")
            print("   • Login with shared parent/guardian phone number")
            print("   • View combined student data (e.g., 'Rakib & Rahim')")
            print("\n📝 Next Steps:")
            print("   1. Run: python test_session_features.py")
            print("   2. Test multi-student login at: http://127.0.0.1:5000")
            print("   3. Use password: student123 for all students")
            print()
            
            return True
            
        except Exception as e:
            print(f"\n❌ Migration failed: {str(e)}")
            print(f"\n🔄 Rolling back changes...")
            db.session.rollback()
            
            # Try to restore from backup if SQLite
            if is_sqlite:
                try:
                    print("   Attempting to restore from backup...")
                    db.session.execute(text("DROP TABLE IF EXISTS users"))
                    db.session.execute(text("ALTER TABLE users_backup RENAME TO users"))
                    db.session.commit()
                    print("   ✅ Restored from backup")
                except:
                    print("   ⚠️  Could not restore automatically")
            
            print(f"\n💡 Error details: {e}")
            return False

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("⚠️  WARNING: Database Migration")
    print("=" * 70)
    print("\nThis script will modify the database schema.")
    print("It will remove the UNIQUE constraint from users.phoneNumber field.")
    print("\n⚠️  Recommendation: Backup your database before proceeding!")
    
    response = input("\nDo you want to continue? (yes/no): ").lower().strip()
    
    if response == 'yes':
        success = migrate_remove_phone_unique_constraint()
        sys.exit(0 if success else 1)
    else:
        print("\n❌ Migration cancelled by user")
        sys.exit(1)
