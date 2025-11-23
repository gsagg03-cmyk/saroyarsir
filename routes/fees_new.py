"""
Fee Management Routes - Completely rewritten for clarity and reliability
"""
from flask import Blueprint, request, jsonify
from models import db, User, Batch, Fee, UserRole, FeeStatus
from sqlalchemy import extract
from datetime import datetime, date
from decimal import Decimal
import calendar

fees_bp = Blueprint('fees', __name__)

def success_response(message, data=None, status=200):
    """Standard success response format"""
    response = {
        'success': True,
        'message': message
    }
    if data:
        response['data'] = data
    return jsonify(response), status

def error_response(message, status=400):
    """Standard error response format"""
    return jsonify({
        'success': False,
        'error': message
    }), status


@fees_bp.route('/load-monthly', methods=['GET'])
def load_monthly_fees():
    """
    Load monthly fees for a batch and year
    GET /api/fees/load-monthly?batch_id=1&year=2025
    
    Returns:
    {
        "success": true,
        "message": "Fees loaded successfully",
        "data": {
            "fees": [
                {
                    "student_id": 1,
                    "student_name": "John Doe",
                    "months": {
                        "1": {"amount": 500, "fee_id": 123, "status": "pending"},
                        "2": {"amount": 0, "fee_id": null, "status": null},
                        ...
                    }
                }
            ],
            "batch_id": 1,
            "year": 2025
        }
    }
    """
    try:
        # Get parameters
        batch_id = request.args.get('batch_id', type=int)
        year = request.args.get('year', type=int)
        
        # Validate parameters
        if not batch_id:
            return error_response('batch_id is required', 400)
        
        if not year:
            year = datetime.now().year
        
        if year < 2020 or year > 2030:
            return error_response('Year must be between 2020 and 2030', 400)
        
        # Check if batch exists
        batch = Batch.query.get(batch_id)
        if not batch:
            return error_response('Batch not found', 404)
        
        # Get all active students in the batch
        students = User.query.filter(
            User.role == UserRole.STUDENT,
            User.is_active == True
        ).join(User.batches).filter(Batch.id == batch_id).order_by(User.first_name).all()
        
        if not students:
            return error_response('No students found in this batch', 404)
        
        # Get all fees for this batch and year
        fees = Fee.query.filter(
            Fee.batch_id == batch_id,
            extract('year', Fee.due_date) == year
        ).all()
        
        # Create a lookup dictionary: student_id -> month -> fee_data
        fees_lookup = {}
        for fee in fees:
            student_id = fee.user_id
            month = fee.due_date.month
            
            if student_id not in fees_lookup:
                fees_lookup[student_id] = {}
            
            fees_lookup[student_id][month] = {
                'jf_amount': float(fee.jf_amount) if hasattr(fee, 'jf_amount') and fee.jf_amount else 0,
                'tf_amount': float(fee.tf_amount) if hasattr(fee, 'tf_amount') and fee.tf_amount else 0,
                'amount': float(fee.amount),
                'fee_id': fee.id,
                'status': fee.status.value,
                'paid_date': fee.paid_date.isoformat() if fee.paid_date else None
            }
        
        # Build response data
        result = []
        for student in students:
            student_data = {
                'student_id': student.id,
                'student_name': student.full_name,
                'exam_fee': float(student.exam_fee) if hasattr(student, 'exam_fee') and student.exam_fee else 0,
                'other_fee': float(student.others_fee) if hasattr(student, 'others_fee') and student.others_fee else 0,
                'months': {}
            }
            
            # Add data for all 12 months
            for month in range(1, 13):
                if student.id in fees_lookup and month in fees_lookup[student.id]:
                    student_data['months'][str(month)] = fees_lookup[student.id][month]
                else:
                    # No fee record for this month
                    student_data['months'][str(month)] = {
                        'jf_amount': 0,
                        'tf_amount': 0,
                        'amount': 0,
                        'fee_id': None,
                        'status': None,
                        'paid_date': None
                    }
            
            result.append(student_data)
        
        return success_response('Fees loaded successfully', {
            'fees': result,
            'batch_id': batch_id,
            'year': year,
            'student_count': len(students)
        })
        
    except Exception as e:
        print(f"Error loading fees: {str(e)}")
        return error_response(f'Failed to load fees: {str(e)}', 500)


@fees_bp.route('/save-monthly', methods=['POST'])
def save_monthly_fee():
    """
    Save a single monthly fee entry
    POST /api/fees/save-monthly
    
    Request body:
    {
        "student_id": 1,
        "batch_id": 1,
        "month": 1,
        "year": 2025,
        "amount": 500
    }
    
    Returns:
    {
        "success": true,
        "message": "Fee saved successfully",
        "data": {
            "fee_id": 123,
            "student_id": 1,
            "month": 1,
            "year": 2025,
            "amount": 500
        }
    }
    """
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return error_response('Request body is required', 400)
        
        # Extract and validate required fields
        student_id = data.get('student_id')
        batch_id = data.get('batch_id')
        month = data.get('month')
        year = data.get('year')
        jf_amount = data.get('jf_amount', 0)
        tf_amount = data.get('tf_amount', 0)
        
        # Backward compatibility: if amount is provided, use it
        amount = data.get('amount')
        if amount is not None and jf_amount == 0 and tf_amount == 0:
            jf_amount = amount
        
        # Validate required fields
        if not all([student_id, batch_id, month, year]):
            return error_response('student_id, batch_id, month, and year are required', 400)
        
        # Validate types and ranges
        try:
            student_id = int(student_id)
            batch_id = int(batch_id)
            month = int(month)
            year = int(year)
            jf_amount = float(jf_amount)
            tf_amount = float(tf_amount)
        except (ValueError, TypeError):
            return error_response('Invalid data types', 400)
        
        if not (1 <= month <= 12):
            return error_response('Month must be between 1 and 12', 400)
        
        if not (2020 <= year <= 2030):
            return error_response('Year must be between 2020 and 2030', 400)
        
        if jf_amount < 0 or tf_amount < 0:
            return error_response('Amounts cannot be negative', 400)
        
        # Calculate total amount for backward compatibility
        total_amount = jf_amount + tf_amount
        
        # Verify student exists and is active
        student = User.query.filter_by(
            id=student_id,
            role=UserRole.STUDENT,
            is_active=True
        ).first()
        
        if not student:
            return error_response('Student not found or inactive', 404)
        
        # Verify batch exists
        batch = Batch.query.get(batch_id)
        if not batch:
            return error_response('Batch not found', 404)
        
        # Verify student is enrolled in the batch
        if batch not in student.batches:
            return error_response('Student is not enrolled in this batch', 400)
        
        # Calculate due date (last day of the month)
        last_day = calendar.monthrange(year, month)[1]
        due_date = date(year, month, last_day)
        
        # Check if fee already exists for this student, batch, month, and year
        existing_fee = Fee.query.filter(
            Fee.user_id == student_id,
            Fee.batch_id == batch_id,
            extract('month', Fee.due_date) == month,
            extract('year', Fee.due_date) == year
        ).first()
        
        if existing_fee:
            # Update or delete existing fee
            if total_amount == 0:
                # Delete fee if both amounts are zero
                db.session.delete(existing_fee)
                db.session.commit()
                return success_response('Fee deleted successfully', {
                    'deleted': True,
                    'student_id': student_id,
                    'month': month,
                    'year': year
                })
            else:
                # Update existing fee
                existing_fee.jf_amount = Decimal(str(jf_amount))
                existing_fee.tf_amount = Decimal(str(tf_amount))
                existing_fee.amount = Decimal(str(total_amount))
                existing_fee.updated_at = datetime.utcnow()
                db.session.commit()
                
                return success_response('Fee updated successfully', {
                    'fee_id': existing_fee.id,
                    'student_id': existing_fee.user_id,
                    'batch_id': existing_fee.batch_id,
                    'month': month,
                    'year': year,
                    'jf_amount': float(existing_fee.jf_amount),
                    'tf_amount': float(existing_fee.tf_amount),
                    'amount': float(existing_fee.amount),
                    'status': existing_fee.status.value
                })
        else:
            # Create new fee
            if total_amount == 0:
                # Don't create a fee with zero amount
                return success_response('No fee created (amount is zero)', {
                    'created': False,
                    'student_id': student_id,
                    'month': month,
                    'year': year
                })
            else:
                # Create new fee record
                new_fee = Fee(
                    user_id=student_id,
                    batch_id=batch_id,
                    jf_amount=Decimal(str(jf_amount)),
                    tf_amount=Decimal(str(tf_amount)),
                    amount=Decimal(str(total_amount)),
                    due_date=due_date,
                    status=FeeStatus.PENDING,
                    notes=f'Monthly fee for {calendar.month_name[month]} {year}'
                )
                
                db.session.add(new_fee)
                db.session.commit()
                
                return success_response('Fee created successfully', {
                    'fee_id': new_fee.id,
                    'student_id': new_fee.user_id,
                    'batch_id': new_fee.batch_id,
                    'month': month,
                    'year': year,
                    'jf_amount': float(new_fee.jf_amount),
                    'tf_amount': float(new_fee.tf_amount),
                    'amount': float(new_fee.amount),
                    'status': new_fee.status.value
                }, 201)
        
    except Exception as e:
        db.session.rollback()
        print(f"Error saving fee: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(f'Failed to save fee: {str(e)}', 500)


@fees_bp.route('/test', methods=['GET'])
def test_endpoint():
    """Simple test endpoint to verify routes are working"""
    return success_response('Fee routes are working!', {
        'timestamp': datetime.utcnow().isoformat(),
        'available_endpoints': [
            'GET /api/fees/load-monthly?batch_id=X&year=Y',
            'POST /api/fees/save-monthly',
            'GET /api/fees/test'
        ]
    })
