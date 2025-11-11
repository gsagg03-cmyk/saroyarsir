"""
Fix online_exams table schema on VPS
This script drops the incomplete table and recreates it with all required columns
"""

from app import create_app
from models import db
from sqlalchemy import text

app = create_app('production')

with app.app_context():
    try:
        print("=" * 60)
        print("FIXING ONLINE EXAMS SCHEMA")
        print("=" * 60)
        
        # Drop existing incomplete table
        print("\n1. Dropping incomplete online_exams table...")
        db.session.execute(text("DROP TABLE IF EXISTS online_exams"))
        db.session.commit()
        print("✅ Dropped online_exams table")
        
        # Create table with complete schema
        print("\n2. Creating online_exams table with complete schema...")
        db.session.execute(text("""
            CREATE TABLE online_exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                class_name VARCHAR(100) NOT NULL,
                book_name VARCHAR(255) NOT NULL,
                chapter_name VARCHAR(255) NOT NULL,
                duration INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                pass_percentage FLOAT DEFAULT 40.0,
                allow_retake BOOLEAN DEFAULT 1,
                is_active BOOLEAN DEFAULT 1,
                is_published BOOLEAN DEFAULT 0,
                created_by INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
        """))
        db.session.commit()
        print("✅ Created online_exams table")
        
        # Drop and recreate online_questions table
        print("\n3. Creating online_questions table...")
        db.session.execute(text("DROP TABLE IF EXISTS online_questions"))
        db.session.commit()
        
        db.session.execute(text("""
            CREATE TABLE online_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_answer VARCHAR(1) NOT NULL,
                explanation TEXT,
                question_order INTEGER DEFAULT 0,
                marks INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (exam_id) REFERENCES online_exams (id) ON DELETE CASCADE
            )
        """))
        db.session.commit()
        print("✅ Created online_questions table")
        
        # Drop and recreate online_exam_attempts table
        print("\n4. Creating online_exam_attempts table...")
        db.session.execute(text("DROP TABLE IF EXISTS online_exam_attempts"))
        db.session.commit()
        
        db.session.execute(text("""
            CREATE TABLE online_exam_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                attempt_number INTEGER DEFAULT 1,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                submitted_at DATETIME,
                time_taken INTEGER,
                is_submitted BOOLEAN DEFAULT 0,
                auto_submitted BOOLEAN DEFAULT 0,
                score INTEGER DEFAULT 0,
                total_marks INTEGER DEFAULT 0,
                percentage FLOAT DEFAULT 0.0,
                is_passed BOOLEAN DEFAULT 0,
                FOREIGN KEY (exam_id) REFERENCES online_exams (id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users (id)
            )
        """))
        db.session.commit()
        print("✅ Created online_exam_attempts table")
        
        # Drop and recreate online_student_answers table
        print("\n5. Creating online_student_answers table...")
        db.session.execute(text("DROP TABLE IF EXISTS online_student_answers"))
        db.session.commit()
        
        db.session.execute(text("""
            CREATE TABLE online_student_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                selected_answer VARCHAR(1),
                is_correct BOOLEAN DEFAULT 0,
                marks_obtained INTEGER DEFAULT 0,
                answered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (attempt_id) REFERENCES online_exam_attempts (id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES online_questions (id),
                UNIQUE (attempt_id, question_id)
            )
        """))
        db.session.commit()
        print("✅ Created online_student_answers table")
        
        # Verify all columns exist
        print("\n6. Verifying online_exams table structure...")
        result = db.session.execute(text("PRAGMA table_info(online_exams)"))
        columns = [row[1] for row in result.fetchall()]
        
        required_columns = [
            'id', 'title', 'description', 'class_name', 'book_name', 
            'chapter_name', 'duration', 'total_questions', 'pass_percentage',
            'allow_retake', 'is_active', 'is_published', 'created_by',
            'created_at', 'updated_at'
        ]
        
        print(f"\nFound columns: {', '.join(columns)}")
        
        missing = [col for col in required_columns if col not in columns]
        if missing:
            print(f"\n❌ MISSING COLUMNS: {', '.join(missing)}")
        else:
            print("\n✅ All required columns present!")
        
        # Verify questions table
        print("\n7. Verifying online_questions table structure...")
        result = db.session.execute(text("PRAGMA table_info(online_questions)"))
        columns = [row[1] for row in result.fetchall()]
        
        required_q_columns = [
            'id', 'exam_id', 'question_text', 'option_a', 'option_b', 
            'option_c', 'option_d', 'correct_answer', 'explanation',
            'question_order', 'marks', 'created_at', 'updated_at'
        ]
        
        print(f"Found columns: {', '.join(columns)}")
        
        missing = [col for col in required_q_columns if col not in columns]
        if missing:
            print(f"\n❌ MISSING COLUMNS: {', '.join(missing)}")
        else:
            print("\n✅ All required columns present in questions table!")
        
        # Verify all tables exist
        print("\n8. Verifying all tables exist...")
        result = db.session.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN (
                'online_exams', 'online_questions', 
                'online_exam_attempts', 'online_student_answers'
            )
        """))
        tables = [row[0] for row in result.fetchall()]
        
        print(f"Found tables: {', '.join(tables)}")
        
        if len(tables) == 4:
            print("\n✅ All 4 tables created successfully!")
        else:
            print(f"\n❌ Only {len(tables)} of 4 tables found")
        
        print("\n" + "=" * 60)
        print("SCHEMA FIX COMPLETE!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        raise
