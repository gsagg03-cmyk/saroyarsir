"""
Test Monthly Exam Creation
Tests the creation of a monthly exam with proper data
"""
from app import create_app, db
from models import User, Batch, MonthlyExam
import json


def test_monthly_exam_creation():
    """Test creating a monthly exam"""
    app = create_app()
    
    with app.app_context():
        with app.test_client() as client:
            print("=" * 80)
            print("TESTING MONTHLY EXAM CREATION")
            print("=" * 80)
            
            # Login as teacher
            print("\n1. Logging in as teacher...")
            login_response = client.post('/api/auth/login', 
                json={'phoneNumber': '01711111111', 'password': 'teacher123'},
                content_type='application/json'
            )
            
            login_data = login_response.get_json()
            print(f"   Status: {login_response.status_code}")
            
            if not login_data.get('success'):
                print(f"   ❌ Login failed: {login_data.get('message')}")
                return
            
            print(f"   ✅ Logged in as: {login_data['data']['user']['name']}")
            
            # Get batches
            print("\n2. Getting batches...")
            batches_response = client.get('/api/batches')
            batches_data = batches_response.get_json()
            
            if not batches_data.get('success') or not batches_data.get('data'):
                print("   ❌ No batches found")
                return
            
            batch_id = batches_data['data'][0]['id']
            batch_name = batches_data['data'][0]['name']
            print(f"   ✅ Using batch: {batch_name} (ID: {batch_id})")
            
            # Check existing monthly exams
            print("\n3. Checking existing monthly exams...")
            existing_response = client.get(f'/api/monthly-exams?batch_id={batch_id}')
            existing_data = existing_response.get_json()
            
            existing_count = len(existing_data.get('data', []))
            print(f"   Existing monthly exams: {existing_count}")
            
            # Create new monthly exam
            print("\n4. Creating new monthly exam...")
            
            create_data = {
                'title': 'Test Monthly Exam - December 2025',
                'description': 'Test exam for debugging',
                'month': 12,
                'year': 2025,
                'batch_id': batch_id,
                'individual_exams': [
                    {
                        'title': 'Mathematics Test',
                        'subject': 'Mathematics',
                        'marks': 30,
                        'exam_date': '2025-12-15T10:00:00Z',
                        'duration': 60
                    },
                    {
                        'title': 'English Test',
                        'subject': 'English',
                        'marks': 25,
                        'exam_date': '2025-12-16T10:00:00Z',
                        'duration': 60
                    }
                ]
            }
            
            print(f"   Request data: {json.dumps(create_data, indent=2)}")
            
            create_response = client.post('/api/monthly-exams',
                json=create_data,
                content_type='application/json'
            )
            
            create_result = create_response.get_json()
            print(f"\n   Status: {create_response.status_code}")
            print(f"   Response: {json.dumps(create_result, indent=2)}")
            
            if create_response.status_code == 201:
                print("\n   ✅ Monthly exam created successfully!")
                exam_id = create_result['data']['monthly_exam']['id']
                print(f"   Exam ID: {exam_id}")
                print(f"   Total Marks: {create_result['data']['monthly_exam']['total_marks']}")
            else:
                print(f"\n   ❌ Failed to create monthly exam")
                print(f"   Error: {create_result.get('message', 'Unknown error')}")
            
            # Verify in database
            print("\n5. Verifying in database...")
            exam_count = MonthlyExam.query.filter_by(batch_id=batch_id).count()
            print(f"   Total monthly exams in database: {exam_count}")
            
            latest_exam = MonthlyExam.query.filter_by(batch_id=batch_id).order_by(MonthlyExam.id.desc()).first()
            if latest_exam:
                print(f"   Latest exam: {latest_exam.title}")
                print(f"   Total marks: {latest_exam.total_marks}")
                print(f"   Individual exams: {len(latest_exam.individual_exams)}")
            
            print("\n" + "=" * 80)


if __name__ == '__main__':
    test_monthly_exam_creation()
