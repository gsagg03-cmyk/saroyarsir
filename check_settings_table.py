"""
Check and create Settings table if missing
This ensures SMS templates can be saved to database
"""

from app import create_app
from models import db
from sqlalchemy import text

app = create_app('production')

with app.app_context():
    try:
        print("=" * 60)
        print("CHECKING SETTINGS TABLE")
        print("=" * 60)
        
        # Check if settings table exists
        result = db.session.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='settings'
        """))
        tables = [row[0] for row in result.fetchall()]
        
        if not tables:
            print("\n❌ Settings table does NOT exist")
            print("\n1. Creating settings table...")
            
            db.session.execute(text("""
                CREATE TABLE settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key VARCHAR(255) UNIQUE NOT NULL,
                    value JSON,
                    description TEXT,
                    category VARCHAR(100),
                    is_public BOOLEAN DEFAULT 0,
                    updated_by INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (updated_by) REFERENCES users (id)
                )
            """))
            db.session.commit()
            print("✅ Settings table created successfully!")
        else:
            print("\n✅ Settings table already exists")
        
        # Verify table structure
        print("\n2. Verifying table structure...")
        result = db.session.execute(text("PRAGMA table_info(settings)"))
        columns = [row[1] for row in result.fetchall()]
        
        required_columns = ['id', 'key', 'value', 'description', 'category', 'is_public', 'updated_by', 'created_at', 'updated_at']
        
        print(f"\nFound columns: {', '.join(columns)}")
        
        missing = [col for col in required_columns if col not in columns]
        if missing:
            print(f"\n❌ MISSING COLUMNS: {', '.join(missing)}")
        else:
            print("\n✅ All required columns present!")
        
        # Test insert and retrieve
        print("\n3. Testing SMS template save/load...")
        
        # Insert a test template
        db.session.execute(text("""
            INSERT OR REPLACE INTO settings (key, value, description, category, updated_by)
            VALUES ('sms_template_test', '{"message": "Test template {student_name}"}', 'Test SMS template', 'sms_templates', NULL)
        """))
        db.session.commit()
        
        # Retrieve it
        result = db.session.execute(text("""
            SELECT key, value FROM settings WHERE key = 'sms_template_test'
        """))
        test_data = result.fetchone()
        
        if test_data:
            print(f"✅ Test template saved and retrieved: {test_data[0]} = {test_data[1]}")
            
            # Clean up test
            db.session.execute(text("DELETE FROM settings WHERE key = 'sms_template_test'"))
            db.session.commit()
        else:
            print("❌ Failed to retrieve test template")
        
        # Check existing SMS templates
        print("\n4. Checking existing SMS templates...")
        result = db.session.execute(text("""
            SELECT key, value FROM settings WHERE key LIKE 'sms_template_%'
        """))
        templates = result.fetchall()
        
        if templates:
            print(f"\n✅ Found {len(templates)} existing SMS template(s):")
            for key, value in templates:
                print(f"  - {key}: {value}")
        else:
            print("\n⚠️  No SMS templates found in database yet")
        
        print("\n" + "=" * 60)
        print("SETTINGS TABLE CHECK COMPLETE!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        raise
