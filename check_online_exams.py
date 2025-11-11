#!/usr/bin/env python3
"""
Check online exams in database
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, OnlineExam, User, UserRole

app = create_app()

with app.app_context():
    print("=== CHECKING ONLINE EXAMS ===\n")
    
    # Get all exams
    exams = OnlineExam.query.all()
    print(f"Total exams in database: {len(exams)}\n")
    
    if exams:
        for exam in exams:
            print(f"Exam ID: {exam.id}")
            print(f"  Title: {exam.title}")
            print(f"  Class: {exam.class_name}")
            print(f"  Book: {exam.book_name}")
            print(f"  Chapter: {exam.chapter_name}")
            print(f"  Questions: {exam.questions.count()}/{exam.total_questions}")
            print(f"  Duration: {exam.duration} minutes")
            print(f"  Published: {exam.is_published}")
            print(f"  Active: {exam.is_active}")
            print(f"  Created: {exam.created_at}")
            print()
    else:
        print("❌ No exams found in database!")
        print("\nTo create an exam:")
        print("1. Login as teacher")
        print("2. Go to Online Exam section")
        print("3. Click 'Create New Exam'")
        print("4. Fill in details and add questions")
        print("5. Click 'Publish' to make it visible to students")
    
    # Check students
    print("\n=== CHECKING STUDENTS ===\n")
    students = User.query.filter_by(role=UserRole.STUDENT).all()
    print(f"Total students: {len(students)}\n")
    
    if students:
        for student in students[:5]:  # Show first 5
            print(f"Student: {student.full_name} (ID: {student.id}, Phone: {student.phoneNumber})")
    
    print("\n=== CHECK COMPLETE ===")
