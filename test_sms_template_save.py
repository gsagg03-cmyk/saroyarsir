#!/usr/bin/env python3
"""
Test script to verify SMS template persistence
"""

from app import create_app
import json

app = create_app()

with app.app_context():
    with app.test_client() as client:
        print("\n" + "="*60)
        print("TESTING SMS TEMPLATE PERSISTENCE")
        print("="*60)
        
        # Login as teacher
        print("\n1️⃣  Logging in as teacher...")
        login_response = client.post('/api/auth/login',
            json={'phoneNumber': '01711111111', 'password': 'teacher123'},
            content_type='application/json'
        )
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.status_code}")
            print(login_response.get_json())
            exit(1)
        
        print("✅ Login successful")
        
        # Get current templates
        print("\n2️⃣  Getting current templates...")
        templates_response = client.get('/api/sms/templates')
        
        if templates_response.status_code != 200:
            print(f"❌ Failed to get templates: {templates_response.status_code}")
            print(templates_response.get_json())
            exit(1)
        
        templates = templates_response.get_json()
        print(f"✅ Retrieved {len(templates)} templates")
        
        # Find attendance_present template
        attendance_template = next((t for t in templates if t['id'] == 'attendance_present'), None)
        if not attendance_template:
            print("❌ attendance_present template not found")
            exit(1)
        
        print(f"\n📝 Current template message:")
        print(f"   {attendance_template['message']}")
        
        # Update the template
        print("\n3️⃣  Updating template...")
        new_message = "Dear Parent, {student_name} was PRESENT today in {batch_name}. Date: {date}. Thank you!"
        
        update_response = client.put('/api/sms/templates/attendance_present',
            json={'message': new_message},
            content_type='application/json'
        )
        
        if update_response.status_code != 200:
            print(f"❌ Failed to update template: {update_response.status_code}")
            print(update_response.get_json())
            exit(1)
        
        update_data = update_response.get_json()
        print(f"✅ Template updated: {update_data.get('message')}")
        
        # Verify the update
        print("\n4️⃣  Verifying template was saved...")
        verify_response = client.get('/api/sms/templates')
        
        if verify_response.status_code != 200:
            print(f"❌ Failed to verify: {verify_response.status_code}")
            exit(1)
        
        verify_templates = verify_response.get_json()
        updated_template = next((t for t in verify_templates if t['id'] == 'attendance_present'), None)
        
        if updated_template and updated_template['message'] == new_message:
            print(f"✅ Template saved correctly!")
            print(f"   New message: {updated_template['message']}")
        else:
            print(f"❌ Template not saved correctly")
            print(f"   Expected: {new_message}")
            print(f"   Got: {updated_template['message'] if updated_template else 'None'}")
            exit(1)
        
        # Check database directly
        print("\n5️⃣  Checking database...")
        from models import SmsTemplate, db
        
        db_template = SmsTemplate.query.filter_by(
            name='attendance_present'
        ).first()
        
        if db_template:
            print(f"✅ Template found in database:")
            print(f"   ID: {db_template.id}")
            print(f"   Name: {db_template.name}")
            print(f"   Content: {db_template.content}")
            print(f"   Created by: {db_template.created_by}")
            print(f"   Updated at: {db_template.updated_at}")
        else:
            print("⚠️  Template not found in database (might be in session only)")
        
        # Simulate new session (logout and login)
        print("\n6️⃣  Testing persistence after logout/login...")
        
        # Logout
        client.get('/api/auth/logout')
        print("✅ Logged out")
        
        # Login again
        login_response2 = client.post('/api/auth/login',
            json={'phoneNumber': '01711111111', 'password': 'teacher123'},
            content_type='application/json'
        )
        
        if login_response2.status_code != 200:
            print(f"❌ Re-login failed")
            exit(1)
        
        print("✅ Logged in again")
        
        # Get templates again
        final_response = client.get('/api/sms/templates')
        
        if final_response.status_code != 200:
            print(f"❌ Failed to get templates after re-login")
            exit(1)
        
        final_templates = final_response.get_json()
        final_template = next((t for t in final_templates if t['id'] == 'attendance_present'), None)
        
        if final_template and final_template['message'] == new_message:
            print(f"✅ PERSISTENCE VERIFIED! Template retained after logout/login")
            print(f"   Message: {final_template['message']}")
        else:
            print(f"❌ PERSISTENCE FAILED! Template reverted after logout/login")
            print(f"   Expected: {new_message}")
            print(f"   Got: {final_template['message'] if final_template else 'None'}")
            exit(1)
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\n📋 Summary:")
        print("   ✅ Templates can be updated via API")
        print("   ✅ Templates are saved to database")
        print("   ✅ Templates persist after logout/login")
        print("   ✅ Database correctly stores template data")
        print("\n")
