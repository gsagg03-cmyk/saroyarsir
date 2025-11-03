#!/usr/bin/env python3
"""Create demo monthly exam data for testing"""

from app import create_app
from models import db, User, Batch, MonthlyExam, IndividualExam, MonthlyMark, MonthlyRanking, UserRole
from datetime import datetime, timedelta
import random

def create_demo_data():
    app = create_app()
    with app.app_context():
        print("🔍 Finding batch and students...")
        
        # Get the Class 10 Mathematics batch
        batch = Batch.query.filter_by(name="Class 10 Mathematics").first()
        if not batch:
            print("❌ No 'Class 10 Mathematics' batch found!")
            print("Available batches:")
            for b in Batch.query.all():
                print(f"  - {b.name}")
            return
        
        print(f"✅ Found batch: {batch.name}")
        
        # Get students in the batch
        students = [s for s in batch.students if s.role == UserRole.STUDENT and s.is_active and not s.is_archived]
        print(f"✅ Found {len(students)} active students")
        
        if len(students) < 2:
            print("❌ Need at least 2 students in the batch")
            return
        
        # Get or create a teacher for created_by
        teacher = User.query.filter_by(role=UserRole.TEACHER).first()
        if not teacher:
            teacher = User.query.filter_by(role=UserRole.SUPER_USER).first()
        
        if not teacher:
            print("❌ No teacher or admin found!")
            return
        
        print(f"✅ Using teacher: {teacher.full_name}")
        
        # Create monthly exam
        print("\n📝 Creating November 2025 Monthly Exam...")
        
        # Check if already exists
        existing = MonthlyExam.query.filter_by(
            batch_id=batch.id,
            month=11,
            year=2025
        ).first()
        
        if existing:
            print(f"⚠️  Monthly exam already exists (ID: {existing.id})")
            monthly_exam = existing
        else:
            monthly_exam = MonthlyExam(
                title="November 2025 Monthly Exam",
                description="Monthly examination for November 2025",
                month=11,
                year=2025,
                total_marks=300,  # Will be updated based on individual exams
                pass_marks=120,
                start_date=datetime(2025, 11, 1),
                end_date=datetime(2025, 11, 30),
                batch_id=batch.id,
                status='active',
                show_results=True,
                created_by=teacher.id
            )
            db.session.add(monthly_exam)
            db.session.commit()
            print(f"✅ Created monthly exam (ID: {monthly_exam.id})")
        
        # Create individual exams
        print("\n📚 Creating individual exams...")
        
        subjects = [
            {"title": "Mathematics Exam", "subject": "Mathematics", "marks": 100, "duration": 120},
            {"title": "English Exam", "subject": "English", "marks": 100, "duration": 90},
            {"title": "Science Exam", "subject": "Science", "marks": 100, "duration": 120}
        ]
        
        individual_exams = []
        for idx, subject_data in enumerate(subjects):
            existing_exam = IndividualExam.query.filter_by(
                monthly_exam_id=monthly_exam.id,
                subject=subject_data['subject']
            ).first()
            
            if existing_exam:
                print(f"  ⚠️  {subject_data['subject']} exam already exists")
                individual_exams.append(existing_exam)
            else:
                exam = IndividualExam(
                    monthly_exam_id=monthly_exam.id,
                    title=subject_data['title'],
                    subject=subject_data['subject'],
                    marks=subject_data['marks'],
                    exam_date=datetime(2025, 11, 5 + idx * 3),
                    duration=subject_data['duration'],
                    order_index=idx,
                    is_completed=True
                )
                db.session.add(exam)
                individual_exams.append(exam)
                print(f"  ✅ Created {subject_data['subject']} exam")
        
        db.session.commit()
        
        # Update monthly exam total marks
        monthly_exam.total_marks = sum(exam.marks for exam in individual_exams)
        db.session.commit()
        print(f"✅ Updated total marks to {monthly_exam.total_marks}")
        
        # Create marks for students
        print("\n📊 Creating student marks...")
        
        for student in students:
            # Check if marks already exist
            existing_marks = MonthlyMark.query.filter_by(
                monthly_exam_id=monthly_exam.id,
                user_id=student.id
            ).first()
            
            if existing_marks:
                print(f"  ⚠️  Marks already exist for {student.full_name}")
                continue
            
            total_obtained = 0
            
            for exam in individual_exams:
                # Generate random marks (60-95% of total)
                percentage = random.uniform(0.60, 0.95)
                marks_obtained = int(exam.marks * percentage)
                total_obtained += marks_obtained
                
                # Calculate percentage for this exam
                exam_percentage = (marks_obtained / exam.marks) * 100
                
                # Calculate grade for this exam
                if exam_percentage >= 80:
                    grade, gpa = 'A+', 5.0
                elif exam_percentage >= 70:
                    grade, gpa = 'A', 4.0
                elif exam_percentage >= 60:
                    grade, gpa = 'A-', 3.5
                elif exam_percentage >= 50:
                    grade, gpa = 'B', 3.0
                elif exam_percentage >= 40:
                    grade, gpa = 'C', 2.0
                else:
                    grade, gpa = 'F', 0.0
                
                mark = MonthlyMark(
                    monthly_exam_id=monthly_exam.id,
                    user_id=student.id,
                    individual_exam_id=exam.id,
                    marks_obtained=marks_obtained,
                    total_marks=exam.marks,
                    percentage=exam_percentage,
                    grade=grade,
                    gpa=gpa
                )
                db.session.add(mark)
            
            print(f"  ✅ Created marks for {student.full_name}: {total_obtained}/{monthly_exam.total_marks}")
        
        db.session.commit()
        
        # Calculate rankings
        print("\n🏆 Calculating rankings...")
        
        # Delete existing rankings
        MonthlyRanking.query.filter_by(monthly_exam_id=monthly_exam.id).delete()
        
        # Calculate total marks for each student
        student_totals = []
        for student in students:
            marks = MonthlyMark.query.filter_by(
                monthly_exam_id=monthly_exam.id,
                user_id=student.id
            ).all()
            
            if marks:
                total = sum(m.marks_obtained for m in marks)
                percentage = (total / monthly_exam.total_marks) * 100
                
                # Calculate grade
                if percentage >= 80:
                    grade = 'A+'
                    gpa = 5.0
                elif percentage >= 70:
                    grade = 'A'
                    gpa = 4.0
                elif percentage >= 60:
                    grade = 'A-'
                    gpa = 3.5
                elif percentage >= 50:
                    grade = 'B'
                    gpa = 3.0
                elif percentage >= 40:
                    grade = 'C'
                    gpa = 2.0
                else:
                    grade = 'F'
                    gpa = 0.0
                
                student_totals.append({
                    'student': student,
                    'total': total,
                    'percentage': percentage,
                    'grade': grade,
                    'gpa': gpa
                })
        
        # Sort by total marks (descending)
        student_totals.sort(key=lambda x: x['total'], reverse=True)
        
        # Create rankings
        for rank, data in enumerate(student_totals, start=1):
            ranking = MonthlyRanking(
                monthly_exam_id=monthly_exam.id,
                user_id=data['student'].id,
                position=rank,
                total_exam_marks=data['total'],
                total_possible_marks=monthly_exam.total_marks,
                final_total=data['total'],
                max_possible_total=monthly_exam.total_marks,
                percentage=data['percentage'],
                grade=data['grade'],
                gpa=data['gpa']
            )
            db.session.add(ranking)
            print(f"  {rank}. {data['student'].full_name}: {data['total']}/{monthly_exam.total_marks} ({data['percentage']:.1f}%) - Grade {data['grade']}")
        
        db.session.commit()
        
        print("\n" + "="*60)
        print("🎉 DEMO DATA CREATED SUCCESSFULLY!")
        print("="*60)
        print(f"\n✅ Monthly Exam: {monthly_exam.title}")
        print(f"✅ Individual Exams: {len(individual_exams)}")
        print(f"✅ Students with marks: {len(students)}")
        print(f"✅ Rankings calculated: {len(student_totals)}")
        print("\n📱 Login with: 01700000001 / student123")
        print("   Click 'Monthly Exams' to see the results!")
        print("="*60)

if __name__ == '__main__':
    create_demo_data()
