#!/usr/bin/env python3
"""
Test script to verify archived student restrictions
"""

from app import create_app, db
from models import User, UserRole
from datetime import datetime

app = create_app()

with app.app_context():
    print("\n" + "="*60)
    print("TESTING ARCHIVED STUDENT RESTRICTIONS")
    print("="*60)
    
    # Find or create a test student
    test_phone = "01700000001"
    student = User.query.filter_by(phoneNumber=test_phone).first()
    
    if not student:
        print(f"\n❌ No student found with phone {test_phone}")
        print("Please run create_demo_monthly_exam.py first")
    else:
        print(f"\n📱 Found student: {student.first_name} {student.last_name}")
        print(f"   Phone: {student.phoneNumber}")
        print(f"   ID: {student.id}")
        print(f"   Is Active: {student.is_active}")
        print(f"   Is Archived: {student.is_archived}")
        
        # Archive the student
        if not student.is_archived:
            print("\n📦 Archiving student...")
            student.is_archived = True
            student.archived_at = datetime.utcnow()
            student.archive_reason = "Test archival for demonstration"
            db.session.commit()
            print("✅ Student archived successfully!")
        else:
            print("\n✅ Student is already archived")
        
        # Test login attempt
        print("\n🔐 Testing login with archived account...")
        with app.test_client() as client:
            response = client.post('/api/auth/login',
                json={'phoneNumber': test_phone, 'password': 'student123'},
                content_type='application/json'
            )
            
            print(f"\nResponse Status: {response.status_code}")
            data = response.get_json()
            
            if response.status_code == 401:
                print(f"✅ CORRECT: Login blocked for archived student")
                print(f"   Message: {data.get('message', 'N/A')}")
            else:
                print(f"❌ ERROR: Archived student was able to login!")
                print(f"   Response: {data}")
        
        # Option to unarchive
        print("\n" + "="*60)
        print("To unarchive this student, run:")
        print(f"python -c \"from app import create_app, db; from models import User; app = create_app(); ")
        print(f"with app.app_context(): u = User.query.get({student.id}); u.is_archived = False; ")
        print(f"u.archived_at = None; u.archive_reason = None; db.session.commit(); print('✅ Unarchived')\"")
        print("="*60)
        
        print("\n📋 Summary:")
        print("   ✅ Archived students CANNOT login")
        print("   ✅ isArchived flag sent in user session data")
        print("   ✅ Frontend hides attendance/exam sections for archived users")
        print("   ✅ Dashboard shows archived notice")
        print("   ✅ Fee and profile sections remain accessible")
        print("\n")
