"""
Online Exam Routes - MCQ Exam System
Teacher can create class-wise exams with questions
Students can take exams with auto-submit and instant results
"""

from flask import Blueprint, request, jsonify, current_app
from models import db, OnlineExam, OnlineQuestion, OnlineExamAttempt, OnlineStudentAnswer, User, UserRole
from utils.auth import login_required, get_current_user, require_role
from utils.response import success_response, error_response
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_

online_exams_bp = Blueprint('online_exams', __name__, url_prefix='/api/online-exams')

#############################################################################
# TEACHER ROUTES - Exam Management
#############################################################################

@online_exams_bp.route('', methods=['GET'])
@login_required
def get_exams():
    """Get all online exams (teachers see all, students see only published)"""
    try:
        current_user = get_current_user()
        
        if current_user.role in [UserRole.TEACHER, UserRole.SUPER_USER]:
            # Teachers see all exams
            exams = OnlineExam.query.order_by(OnlineExam.created_at.desc()).all()
        else:
            # Students see only published exams
            exams = OnlineExam.query.filter_by(is_published=True, is_active=True).order_by(OnlineExam.created_at.desc()).all()
        
        exams_data = []
        for exam in exams:
            exam_dict = {
                'id': exam.id,
                'title': exam.title,
                'description': exam.description,
                'class_name': exam.class_name,
                'book_name': exam.book_name,
                'chapter_name': exam.chapter_name,
                'duration': exam.duration,
                'total_questions': exam.total_questions,
                'pass_percentage': exam.pass_percentage,
                'allow_retake': exam.allow_retake,
                'is_active': exam.is_active,
                'is_published': exam.is_published,
                'created_at': exam.created_at.isoformat() if exam.created_at else None,
                'questions_count': exam.questions.count(),
            }
            
            # Add attempt info for students
            if current_user.role == UserRole.STUDENT:
                attempts = OnlineExamAttempt.query.filter_by(
                    exam_id=exam.id,
                    student_id=current_user.id,
                    is_submitted=True
                ).order_by(OnlineExamAttempt.submitted_at.desc()).all()
                
                exam_dict['attempts_count'] = len(attempts)
                exam_dict['best_score'] = max([a.percentage for a in attempts]) if attempts else 0
                exam_dict['can_retake'] = exam.allow_retake or len(attempts) == 0
                
                # Check if there's an ongoing attempt
                ongoing = OnlineExamAttempt.query.filter_by(
                    exam_id=exam.id,
                    student_id=current_user.id,
                    is_submitted=False
                ).first()
                exam_dict['has_ongoing_attempt'] = ongoing is not None
                if ongoing:
                    exam_dict['ongoing_attempt_id'] = ongoing.id
                    exam_dict['ongoing_started_at'] = ongoing.started_at.isoformat()
            
            exams_data.append(exam_dict)
        
        return success_response('Exams retrieved successfully', exams_data)
    
    except Exception as e:
        current_app.logger.error(f'Error getting exams: {str(e)}')
        return error_response(f'Failed to get exams: {str(e)}', 500)

@online_exams_bp.route('', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def create_exam():
    """Create a new online exam"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['title', 'class_name', 'book_name', 'chapter_name', 'duration', 'total_questions']
        for field in required_fields:
            if field not in data:
                return error_response(f'Missing required field: {field}', 400)
        
        # Validate total_questions (max 40)
        total_questions = int(data['total_questions'])
        if total_questions < 1 or total_questions > 40:
            return error_response('Total questions must be between 1 and 40', 400)
        
        # Create exam with defaults for optional fields
        exam = OnlineExam(
            title=data['title'],
            description=data.get('description', ''),
            class_name=data['class_name'],
            book_name=data['book_name'],
            chapter_name=data['chapter_name'],
            duration=int(data['duration']),
            total_questions=total_questions,
            pass_percentage=float(data.get('pass_percentage', 40.0)),  # Default 40%
            allow_retake=data.get('allow_retake', True),
            is_active=data.get('is_active', True),
            is_published=False,  # Not published by default
            created_by=current_user.id
        )
        
        db.session.add(exam)
        db.session.commit()
        
        return success_response('Exam created successfully. Now add questions to it.', {
            'id': exam.id,
            'title': exam.title,
            'total_questions': exam.total_questions,
            'questions_to_add': exam.total_questions
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating exam: {str(e)}')
        return error_response(f'Failed to create exam: {str(e)}', 500)

@online_exams_bp.route('/<int:exam_id>', methods=['GET'])
@login_required
def get_exam_details(exam_id):
    """Get exam details with questions (teachers see all, students see only if published)"""
    try:
        current_user = get_current_user()
        exam = OnlineExam.query.get(exam_id)
        
        if not exam:
            return error_response('Exam not found', 404)
        
        # Check permissions
        if current_user.role == UserRole.STUDENT and not exam.is_published:
            return error_response('This exam is not available yet', 403)
        
        exam_data = {
            'id': exam.id,
            'title': exam.title,
            'description': exam.description,
            'class_name': exam.class_name,
            'book_name': exam.book_name,
            'chapter_name': exam.chapter_name,
            'duration': exam.duration,
            'total_questions': exam.total_questions,
            'pass_percentage': exam.pass_percentage,
            'allow_retake': exam.allow_retake,
            'is_active': exam.is_active,
            'is_published': exam.is_published,
            'created_at': exam.created_at.isoformat() if exam.created_at else None,
        }
        
        # Include questions for teachers or for students taking the exam
        if current_user.role in [UserRole.TEACHER, UserRole.SUPER_USER]:
            questions = OnlineQuestion.query.filter_by(exam_id=exam_id).order_by(OnlineQuestion.question_order).all()
            exam_data['questions'] = [{
                'id': q.id,
                'question_text': q.question_text,
                'option_a': q.option_a,
                'option_b': q.option_b,
                'option_c': q.option_c,
                'option_d': q.option_d,
                'correct_answer': q.correct_answer,
                'explanation': q.explanation,
                'question_order': q.question_order,
                'marks': q.marks
            } for q in questions]
        
        return success_response('Exam details retrieved successfully', exam_data)
    
    except Exception as e:
        current_app.logger.error(f'Error getting exam details: {str(e)}')
        return error_response(f'Failed to get exam details: {str(e)}', 500)

@online_exams_bp.route('/<int:exam_id>', methods=['PUT'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def update_exam(exam_id):
    """Update exam details"""
    try:
        exam = OnlineExam.query.get(exam_id)
        if not exam:
            return error_response('Exam not found', 404)
        
        data = request.get_json()
        
        # Update fields
        if 'title' in data:
            exam.title = data['title']
        if 'description' in data:
            exam.description = data['description']
        if 'class_name' in data:
            exam.class_name = data['class_name']
        if 'book_name' in data:
            exam.book_name = data['book_name']
        if 'chapter_name' in data:
            exam.chapter_name = data['chapter_name']
        if 'duration' in data:
            exam.duration = int(data['duration'])
        if 'pass_percentage' in data:
            exam.pass_percentage = float(data['pass_percentage'])
        if 'allow_retake' in data:
            exam.allow_retake = data['allow_retake']
        if 'is_active' in data:
            exam.is_active = data['is_active']
        if 'is_published' in data:
            exam.is_published = data['is_published']
        
        db.session.commit()
        
        return success_response('Exam updated successfully')
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error updating exam: {str(e)}')
        return error_response(f'Failed to update exam: {str(e)}', 500)

@online_exams_bp.route('/<int:exam_id>', methods=['DELETE'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def delete_exam(exam_id):
    """Delete exam and all associated data (CASCADE)"""
    try:
        exam = OnlineExam.query.get(exam_id)
        if not exam:
            return error_response('Exam not found', 404)
        
        exam_title = exam.title
        db.session.delete(exam)
        db.session.commit()
        
        return success_response(f'Exam "{exam_title}" deleted successfully with all questions and attempts')
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting exam: {str(e)}')
        return error_response(f'Failed to delete exam: {str(e)}', 500)

#############################################################################
# QUESTION MANAGEMENT ROUTES
#############################################################################

@online_exams_bp.route('/<int:exam_id>/questions', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def add_question(exam_id):
    """Add a question to an exam"""
    try:
        exam = OnlineExam.query.get(exam_id)
        if not exam:
            return error_response('Exam not found', 404)
        
        # Check if exam already has max questions
        current_count = OnlineQuestion.query.filter_by(exam_id=exam_id).count()
        if current_count >= exam.total_questions:
            return error_response(f'Exam already has maximum {exam.total_questions} questions', 400)
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer']
        for field in required_fields:
            if field not in data or not data[field]:
                return error_response(f'Missing or empty required field: {field}', 400)
        
        # Validate correct_answer
        correct_answer = data['correct_answer'].upper()
        if correct_answer not in ['A', 'B', 'C', 'D']:
            return error_response('Correct answer must be A, B, C, or D', 400)
        
        # Create question
        question = OnlineQuestion(
            exam_id=exam_id,
            question_text=data['question_text'],
            option_a=data['option_a'],
            option_b=data['option_b'],
            option_c=data['option_c'],
            option_d=data['option_d'],
            correct_answer=correct_answer,
            explanation=data.get('explanation', ''),
            question_order=current_count + 1,
            marks=int(data.get('marks', 1))
        )
        
        db.session.add(question)
        db.session.commit()
        
        new_count = current_count + 1
        return success_response(f'Question added successfully ({new_count}/{exam.total_questions})', {
            'id': question.id,
            'question_order': question.question_order,
            'questions_added': new_count,
            'questions_remaining': exam.total_questions - new_count
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error adding question: {str(e)}')
        return error_response(f'Failed to add question: {str(e)}', 500)

@online_exams_bp.route('/<int:exam_id>/questions/<int:question_id>', methods=['PUT'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def update_question(exam_id, question_id):
    """Update a question"""
    try:
        question = OnlineQuestion.query.filter_by(id=question_id, exam_id=exam_id).first()
        if not question:
            return error_response('Question not found', 404)
        
        data = request.get_json()
        
        # Update fields
        if 'question_text' in data:
            question.question_text = data['question_text']
        if 'option_a' in data:
            question.option_a = data['option_a']
        if 'option_b' in data:
            question.option_b = data['option_b']
        if 'option_c' in data:
            question.option_c = data['option_c']
        if 'option_d' in data:
            question.option_d = data['option_d']
        if 'correct_answer' in data:
            correct_answer = data['correct_answer'].upper()
            if correct_answer not in ['A', 'B', 'C', 'D']:
                return error_response('Correct answer must be A, B, C, or D', 400)
            question.correct_answer = correct_answer
        if 'explanation' in data:
            question.explanation = data['explanation']
        if 'marks' in data:
            question.marks = int(data['marks'])
        
        db.session.commit()
        
        return success_response('Question updated successfully')
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error updating question: {str(e)}')
        return error_response(f'Failed to update question: {str(e)}', 500)

@online_exams_bp.route('/<int:exam_id>/questions/<int:question_id>', methods=['DELETE'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def delete_question(exam_id, question_id):
    """Delete a question"""
    try:
        question = OnlineQuestion.query.filter_by(id=question_id, exam_id=exam_id).first()
        if not question:
            return error_response('Question not found', 404)
        
        db.session.delete(question)
        
        # Reorder remaining questions
        remaining_questions = OnlineQuestion.query.filter_by(exam_id=exam_id).order_by(OnlineQuestion.question_order).all()
        for idx, q in enumerate(remaining_questions):
            q.question_order = idx + 1
        
        db.session.commit()
        
        return success_response('Question deleted successfully')
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting question: {str(e)}')
        return error_response(f'Failed to delete question: {str(e)}', 500)

#############################################################################
# STUDENT ROUTES - Taking Exams
#############################################################################

@online_exams_bp.route('/<int:exam_id>/start', methods=['POST'])
@login_required
@require_role(UserRole.STUDENT)
def start_exam(exam_id):
    """Start an exam attempt"""
    try:
        current_user = get_current_user()
        exam = OnlineExam.query.get(exam_id)
        
        if not exam:
            return error_response('Exam not found', 404)
        
        if not exam.is_published or not exam.is_active:
            return error_response('This exam is not available', 403)
        
        # Check if there's already an ongoing attempt
        ongoing = OnlineExamAttempt.query.filter_by(
            exam_id=exam_id,
            student_id=current_user.id,
            is_submitted=False
        ).first()
        
        if ongoing:
            # Check if time has expired
            time_elapsed = int((datetime.utcnow() - ongoing.started_at).total_seconds())
            time_limit = exam.duration * 60
            
            if time_elapsed >= time_limit:
                # Auto-submit
                return error_response('Time has expired. Please submit the exam.', 400)
            
            # Return the ongoing attempt
            questions = OnlineQuestion.query.filter_by(exam_id=exam_id).order_by(OnlineQuestion.question_order).all()
            questions_data = [{
                'id': q.id,
                'question_text': q.question_text,
                'option_a': q.option_a,
                'option_b': q.option_b,
                'option_c': q.option_c,
                'option_d': q.option_d,
                'question_order': q.question_order,
                'marks': q.marks
            } for q in questions]
            
            # Get existing answers
            existing_answers = OnlineStudentAnswer.query.filter_by(attempt_id=ongoing.id).all()
            answers_map = {a.question_id: a.selected_answer for a in existing_answers}
            
            return success_response('Continuing existing attempt', {
                'attempt_id': ongoing.id,
                'started_at': ongoing.started_at.isoformat(),
                'time_remaining': time_limit - time_elapsed,
                'questions': questions_data,
                'saved_answers': answers_map,
                'exam': {
                    'id': exam.id,
                    'title': exam.title,
                    'duration': exam.duration,
                    'total_questions': exam.total_questions
                }
            })
        
        # Check if retakes are allowed
        previous_attempts = OnlineExamAttempt.query.filter_by(
            exam_id=exam_id,
            student_id=current_user.id,
            is_submitted=True
        ).count()
        
        if previous_attempts > 0 and not exam.allow_retake:
            return error_response('Retakes are not allowed for this exam', 403)
        
        # Check if exam has enough questions
        questions_count = OnlineQuestion.query.filter_by(exam_id=exam_id).count()
        if questions_count < exam.total_questions:
            return error_response('This exam is not complete yet', 400)
        
        # Create new attempt
        attempt = OnlineExamAttempt(
            exam_id=exam_id,
            student_id=current_user.id,
            attempt_number=previous_attempts + 1,
            total_marks=questions_count  # Assuming 1 mark per question
        )
        
        db.session.add(attempt)
        db.session.commit()
        
        # Get questions (without correct answers)
        questions = OnlineQuestion.query.filter_by(exam_id=exam_id).order_by(OnlineQuestion.question_order).all()
        questions_data = [{
            'id': q.id,
            'question_text': q.question_text,
            'option_a': q.option_a,
            'option_b': q.option_b,
            'option_c': q.option_c,
            'option_d': q.option_d,
            'question_order': q.question_order,
            'marks': q.marks
        } for q in questions]
        
        return success_response('Exam started successfully', {
            'attempt_id': attempt.id,
            'exam': {
                'id': exam.id,
                'title': exam.title,
                'duration': exam.duration,
                'total_questions': exam.total_questions
            },
            'questions': questions_data,
            'started_at': attempt.started_at.isoformat(),
            'duration_minutes': exam.duration,
            'saved_answers': {}
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error starting exam: {str(e)}')
        return error_response(f'Failed to start exam: {str(e)}', 500)

@online_exams_bp.route('/attempts/<int:attempt_id>/answer', methods=['POST'])
@login_required
@require_role(UserRole.STUDENT)
def save_answer(attempt_id):
    """Save/update a student's answer for a question"""
    try:
        current_user = get_current_user()
        attempt = OnlineExamAttempt.query.get(attempt_id)
        
        if not attempt:
            return error_response('Attempt not found', 404)
        
        if attempt.student_id != current_user.id:
            return error_response('Unauthorized', 403)
        
        if attempt.is_submitted:
            return error_response('Exam already submitted', 400)
        
        data = request.get_json()
        question_id = data.get('question_id')
        selected_answer = data.get('selected_answer', '').upper() if data.get('selected_answer') else None
        
        if not question_id:
            return error_response('Question ID required', 400)
        
        if selected_answer and selected_answer not in ['A', 'B', 'C', 'D']:
            return error_response('Invalid answer option', 400)
        
        # Check if answer already exists
        student_answer = OnlineStudentAnswer.query.filter_by(
            attempt_id=attempt_id,
            question_id=question_id
        ).first()
        
        if student_answer:
            # Update existing answer
            student_answer.selected_answer = selected_answer
            student_answer.answered_at = datetime.utcnow()
        else:
            # Create new answer
            student_answer = OnlineStudentAnswer(
                attempt_id=attempt_id,
                question_id=question_id,
                selected_answer=selected_answer
            )
            db.session.add(student_answer)
        
        db.session.commit()
        
        return success_response('Answer saved successfully')
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error saving answer: {str(e)}')
        return error_response(f'Failed to save answer: {str(e)}', 500)

@online_exams_bp.route('/attempts/<int:attempt_id>/submit', methods=['POST'])
@login_required
@require_role(UserRole.STUDENT)
def submit_exam(attempt_id):
    """Submit exam and calculate results"""
    try:
        current_user = get_current_user()
        attempt = OnlineExamAttempt.query.get(attempt_id)
        
        if not attempt:
            return error_response('Attempt not found', 404)
        
        if attempt.student_id != current_user.id:
            return error_response('Unauthorized', 403)
        
        if attempt.is_submitted:
            return error_response('Exam already submitted', 400)
        
        # Check if auto-submit due to timeout
        data = request.get_json() or {}
        auto_submit = data.get('auto_submit', False)
        
        # Calculate time taken
        time_taken = int((datetime.utcnow() - attempt.started_at).total_seconds())
        
        # Get all questions for this exam
        questions = OnlineQuestion.query.filter_by(exam_id=attempt.exam_id).all()
        
        # Calculate score
        total_score = 0
        total_marks = sum(q.marks for q in questions)
        
        for question in questions:
            # Get student's answer
            student_answer = OnlineStudentAnswer.query.filter_by(
                attempt_id=attempt_id,
                question_id=question.id
            ).first()
            
            if student_answer and student_answer.selected_answer == question.correct_answer:
                # Correct answer
                student_answer.is_correct = True
                student_answer.marks_obtained = question.marks
                total_score += question.marks
            elif student_answer:
                # Wrong answer
                student_answer.is_correct = False
                student_answer.marks_obtained = 0
            else:
                # No answer submitted - create record
                student_answer = OnlineStudentAnswer(
                    attempt_id=attempt_id,
                    question_id=question.id,
                    selected_answer=None,
                    is_correct=False,
                    marks_obtained=0
                )
                db.session.add(student_answer)
        
        # Update attempt
        attempt.is_submitted = True
        attempt.submitted_at = datetime.utcnow()
        attempt.time_taken = time_taken
        attempt.score = total_score
        attempt.total_marks = total_marks
        attempt.percentage = (total_score / total_marks * 100) if total_marks > 0 else 0
        attempt.is_passed = attempt.percentage >= attempt.exam.pass_percentage
        attempt.auto_submitted = auto_submit
        
        db.session.commit()
        
        return success_response('Exam submitted successfully', {
            'attempt_id': attempt.id,
            'score': total_score,
            'total_marks': total_marks,
            'percentage': round(attempt.percentage, 2),
            'is_passed': attempt.is_passed,
            'time_taken': time_taken,
            'auto_submitted': auto_submit
        })
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error submitting exam: {str(e)}')
        return error_response(f'Failed to submit exam: {str(e)}', 500)

@online_exams_bp.route('/attempts/<int:attempt_id>/results', methods=['GET'])
@login_required
def get_exam_results(attempt_id):
    """Get detailed exam results with explanations"""
    try:
        current_user = get_current_user()
        attempt = OnlineExamAttempt.query.get(attempt_id)
        
        if not attempt:
            return error_response('Attempt not found', 404)
        
        # Check permissions
        if current_user.role == UserRole.STUDENT and attempt.student_id != current_user.id:
            return error_response('Unauthorized', 403)
        
        if not attempt.is_submitted:
            return error_response('Exam not yet submitted', 400)
        
        # Get all answers with questions
        answers = db.session.query(
            OnlineStudentAnswer, OnlineQuestion
        ).join(
            OnlineQuestion
        ).filter(
            OnlineStudentAnswer.attempt_id == attempt_id
        ).order_by(
            OnlineQuestion.question_order
        ).all()
        
        results_data = []
        for student_answer, question in answers:
            results_data.append({
                'question_id': question.id,
                'question_order': question.question_order,
                'question_text': question.question_text,
                'option_a': question.option_a,
                'option_b': question.option_b,
                'option_c': question.option_c,
                'option_d': question.option_d,
                'correct_answer': question.correct_answer,
                'selected_answer': student_answer.selected_answer,
                'is_correct': student_answer.is_correct,
                'marks_obtained': student_answer.marks_obtained,
                'total_marks': question.marks,
                'explanation': question.explanation if question.explanation else None
            })
        
        return success_response('Results retrieved successfully', {
            'attempt': {
                'id': attempt.id,
                'attempt_number': attempt.attempt_number,
                'score': attempt.score,
                'total_marks': attempt.total_marks,
                'percentage': round(attempt.percentage, 2),
                'is_passed': attempt.is_passed,
                'time_taken': attempt.time_taken,
                'time_taken_formatted': f'{attempt.time_taken // 60}m {attempt.time_taken % 60}s' if attempt.time_taken else None,
                'submitted_at': attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                'auto_submitted': attempt.auto_submitted
            },
            'exam': {
                'id': attempt.exam.id,
                'title': attempt.exam.title,
                'pass_percentage': attempt.exam.pass_percentage,
                'allow_retake': attempt.exam.allow_retake
            },
            'results': results_data
        })
    
    except Exception as e:
        current_app.logger.error(f'Error getting results: {str(e)}')
        return error_response(f'Failed to get results: {str(e)}', 500)
