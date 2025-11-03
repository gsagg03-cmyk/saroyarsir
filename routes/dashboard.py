"""
Dashboard API Routes
Statistics and overview data for dashboard
"""
from flask import Blueprint, jsonify, session
from models import User, Batch, db, UserRole
from utils.auth import login_required, require_role
from utils.response import success_response, error_response

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        # Get counts (exclude archived students)
        total_students = User.query.filter_by(role=UserRole.STUDENT, is_active=True, is_archived=False).count()
        total_teachers = User.query.filter_by(role=UserRole.TEACHER, is_active=True).count()
        total_batches = Batch.query.count()  # Get total count of all batches (active and inactive)
        
        # Calculate pending fees (placeholder for now - you can implement proper fee calculation)
        pending_fees = 0.0  # This would need proper fee management integration
        
        # SMS count (placeholder for now - you can implement proper SMS tracking)
        sms_count = 0  # This would need proper SMS service integration
        
        # Get recent students (last 5, exclude archived)
        recent_students = User.query.filter_by(role=UserRole.STUDENT, is_active=True, is_archived=False)\
                             .order_by(User.created_at.desc())\
                             .limit(5).all()
        
        # Get all batches with student counts (for detailed data, exclude archived students)
        all_batches_data = []
        batches = Batch.query.all()  # Get all batches, not just active ones
        for batch in batches:
            student_count = len([s for s in batch.students if s.role == UserRole.STUDENT and s.is_active and not s.is_archived])
            all_batches_data.append({
                'id': batch.id,
                'name': batch.name,
                'description': batch.description,
                'student_count': student_count,
                'fee_amount': float(batch.fee_amount),
                'is_active': batch.is_active
            })
        
        # Format recent students
        recent_students_data = [{
            'id': student.id,
            'name': f"{student.first_name} {student.last_name}",
            'phoneNumber': student.phoneNumber,
            'email': student.email,
            'created_at': student.created_at.isoformat()
        } for student in recent_students]
        
        # Return stats in the format expected by the frontend
        stats = {
            'totalStudents': total_students,
            'totalBatches': total_batches,
            'pendingFees': pending_fees,
            'smsCount': sms_count,
            'totalTeachers': total_teachers,
            'recentStudents': recent_students_data,
            'allBatchesData': all_batches_data
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return error_response(f'Failed to get dashboard stats: {str(e)}', 500)

@dashboard_bp.route('/overview', methods=['GET'])
@login_required
def get_overview():
    """Get dashboard overview data"""
    try:
        user_id = session.get('user_id')
        current_user = User.query.get(user_id)
        
        if current_user.role == UserRole.STUDENT:
            # Student overview
            student_batches = [{
                'id': batch.id,
                'name': batch.name,
                'description': batch.description,
                'fee_amount': float(batch.fee_amount)
            } for batch in current_user.batches if batch.is_active]
            
            overview = {
                'user_type': 'student',
                'batches': student_batches,
                'batch_count': len(student_batches)
            }
        else:
            # Teacher/Admin overview (exclude archived students)
            overview = {
                'user_type': 'teacher',
                'total_students': User.query.filter_by(role=UserRole.STUDENT, is_active=True, is_archived=False).count(),
                'total_batches': Batch.query.filter_by(is_active=True).count()
            }
        
        return success_response('Overview retrieved successfully', overview)
        
    except Exception as e:
        return error_response(f'Failed to get overview: {str(e)}', 500)