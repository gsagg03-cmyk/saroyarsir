#!/usr/bin/env python3
"""
Test script for session features:
1. Multi-student account (same phone number)
2. Archived student filtering
3. Monthly exam viewing for students
"""

from models import db, User, UserRole, Batch, MonthlyExam, IndividualExam
from datetime import datetime, date
from werkzeug.security import generate_password_hash
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the existing Flask app
from app import create_app
app = create_app()

with app.app_context():
    print("=" * 60)
    print("🧪 TESTING SESSION FEATURES")
    print("=" * 60)
    
    # Find the existing batch
    batch = Batch.query.first()
    if not batch:
        print("❌ No batch found! Please run create_test_data.py first")
        sys.exit(1)
    
    print(f"\n📚 Using batch: {batch.name}")
    
    # Test 1: Create multi-student account
    print("\n" + "=" * 60)
    print("TEST 1: Multi-Student Account (Same Phone Number)")
    print("=" * 60)
    
    # Check if already exists
    existing = User.query.filter_by(phoneNumber='01700000001').first()
    if existing:
        print("⚠️  Multi-student account already exists, skipping creation")
        student1 = User.query.filter_by(phoneNumber='01700000001', first_name='Rakib').first()
        student2 = User.query.filter_by(phoneNumber='01700000001', first_name='Rahim').first()
    else:
        student1 = User(
            phoneNumber='01700000001',
            password_hash=generate_password_hash('student123'),
            first_name='Rakib',
            last_name='Khan',
            role=UserRole.STUDENT,
            is_active=True,
            is_archived=False,
            guardian_phone='01700000001'
        )
        
        student2 = User(
            phoneNumber='01700000001',  # Same phone number!
            password_hash=generate_password_hash('student123'),
            first_name='Rahim',
            last_name='Ahmed',
            role=UserRole.STUDENT,
            is_active=True,
            is_archived=False,
            guardian_phone='01700000001'
        )
        
        db.session.add(student1)
        db.session.add(student2)
        db.session.flush()
        
        # Add both to the batch
        student1.batches.append(batch)
        student2.batches.append(batch)
        db.session.commit()
        
        print("✅ Created multi-student account:")
    
    print(f"   📞 Phone: 01700000001")
    print(f"   👤 Student 1: Rakib Khan (ID: {student1.id if student1 else 'N/A'})")
    print(f"   👤 Student 2: Rahim Ahmed (ID: {student2.id if student2 else 'N/A'})")
    print(f"   🔑 Password: student123")
    print(f"   📚 Batch: {batch.name}")
    
    # Test 2: Create archived student
    print("\n" + "=" * 60)
    print("TEST 2: Archived Student (Should NOT appear in lists)")
    print("=" * 60)
    
    archived = User.query.filter_by(phoneNumber='01700000002').first()
    if archived:
        print("⚠️  Archived student already exists")
    else:
        archived = User(
            phoneNumber='01700000002',
            password_hash=generate_password_hash('student123'),
            first_name='Archived',
            last_name='Student',
            role=UserRole.STUDENT,
            is_active=True,
            is_archived=True,
            archived_at=datetime.utcnow(),
            guardian_phone='01700000002'
        )
        db.session.add(archived)
        db.session.flush()
        archived.batches.append(batch)
        db.session.commit()
        
        print("✅ Created archived student:")
    
    print(f"   📞 Phone: 01700000002")
    print(f"   👤 Name: Archived Student (ID: {archived.id if archived else 'N/A'})")
    print(f"   📦 Status: ARCHIVED")
    
    # Test 3: Create monthly exam
    print("\n" + "=" * 60)
    print("TEST 3: Monthly Exam for Student Viewing")
    print("=" * 60)
    
    monthly_exam = MonthlyExam.query.filter_by(
        batch_id=batch.id,
        month=11,
        year=2025
    ).first()
    
    if monthly_exam:
        print("⚠️  Monthly exam already exists")
    else:
        # Get a teacher or admin to be the creator
        from models import UserRole
        teacher = User.query.filter_by(role=UserRole.TEACHER).first()
        if not teacher:
            teacher = User.query.filter_by(role=UserRole.SUPER_USER).first()
        
        created_by_id = teacher.id if teacher else 1  # Fallback to 1 if no teacher exists
        
        monthly_exam = MonthlyExam(
            title='November 2025 Monthly Exam',
            description='Monthly assessment for November',
            month=11,
            year=2025,
            start_date=date(2025, 11, 1),
            end_date=date(2025, 11, 30),
            batch_id=batch.id,
            total_marks=100,
            pass_marks=40,
            status='active',
            show_results=True,
            created_by=created_by_id
        )
        db.session.add(monthly_exam)
        db.session.flush()
        
        # Create individual exams
        subjects = ['Mathematics', 'English', 'Science']
        for i, subject in enumerate(subjects):
            individual_exam = IndividualExam(
                monthly_exam_id=monthly_exam.id,
                title=f'{subject} Test',
                subject=subject,
                marks=30,
                exam_date=date(2025, 11, 5 + i),
                duration=60,
                order_index=i
            )
            db.session.add(individual_exam)
        
        db.session.commit()
        print("✅ Created monthly exam:")
    
    print(f"   📝 Title: November 2025 Monthly Exam")
    print(f"   📚 Batch: {batch.name}")
    print(f"   📅 Period: Nov 1 - Nov 30, 2025")
    print(f"   📊 Individual Exams: 3 (Mathematics, English, Science)")
    
    # Verification Tests
    print("\n" + "=" * 60)
    print("✅ VERIFICATION TESTS")
    print("=" * 60)
    
    # Test active students (should NOT include archived)
    active_students = User.query.filter_by(
        role=UserRole.STUDENT,
        is_active=True,
        is_archived=False
    ).all()
    
    print(f"\n1️⃣  Active Students Count: {len(active_students)}")
    print(f"   (Should NOT include 'Archived Student')")
    for s in active_students[:10]:
        print(f"   ✓ {s.first_name} {s.last_name} ({s.phoneNumber})")
    
    # Test multi-student query
    multi_students = User.query.filter_by(phoneNumber='01700000001', is_active=True).all()
    print(f"\n2️⃣  Multi-Student Account (01700000001): {len(multi_students)} students")
    for s in multi_students:
        print(f"   ✓ {s.first_name} {s.last_name}")
    
    # Test batch students (should NOT include archived)
    batch_students = [s for s in batch.students if s.is_active and not s.is_archived]
    print(f"\n3️⃣  Batch '{batch.name}' Active Students: {len(batch_students)}")
    print(f"   (Should NOT include 'Archived Student')")
    for s in batch_students[:10]:
        archived_flag = "📦 ARCHIVED" if s.is_archived else ""
        print(f"   ✓ {s.first_name} {s.last_name} {archived_flag}")
    
    # Test monthly exams
    exams = MonthlyExam.query.filter_by(batch_id=batch.id).all()
    print(f"\n4️⃣  Monthly Exams for '{batch.name}': {len(exams)}")
    for exam in exams:
        month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        month_name = month_names[exam.month] if 1 <= exam.month <= 12 else str(exam.month)
        print(f"   ✓ {exam.title} ({month_name} {exam.year})")
    
    print("\n" + "=" * 60)
    print("🎉 TEST DATA CREATED SUCCESSFULLY!")
    print("=" * 60)
    print("\n📋 MANUAL TESTING INSTRUCTIONS:")
    print("=" * 60)
    print("\n1️⃣  Test Multi-Student Account:")
    print("   • Go to: http://127.0.0.1:5000/login")
    print("   • Phone: 01700000001")
    print("   • Password: student123")
    print("   • Expected: Should show 'Rakib & Rahim' as student name")
    print("   • Expected: Should show both students' batches")
    
    print("\n2️⃣  Test Archived Student Filter:")
    print("   • Login as teacher")
    print("   • Go to batch student list")
    print("   • Expected: 'Archived Student' should NOT appear")
    print("   • Check attendance marking")
    print("   • Expected: 'Archived Student' should NOT appear")
    
    print("\n3️⃣  Test Monthly Exam Viewing (Student):")
    print("   • Login as student (01700000001 / student123)")
    print("   • Click 'Monthly Exams' in sidebar")
    print("   • Expected: Should see 'November 2025 Monthly Exam'")
    print("   • Expected: Should have 3 tabs (Monthly Periods, Individual Exams, Results)")
    print("   • Expected: Read-only mode with 'View Only' badge")
    
    print("\n🌐 Application URL: http://127.0.0.1:5000")
    print("=" * 60)
