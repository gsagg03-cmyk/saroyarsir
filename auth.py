"""
Authentication Routes
Login, logout, and session management
"""
from flask import Blueprint, request, jsonify, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from models import db, User, UserRole
from utils.auth import login_required, require_role
from utils.response import success_response, error_response
import re
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

def validate_phone(phone):
    """Validate Bangladeshi phone number format"""
    # Remove any spaces or special characters
    phone = re.sub(r'[^\d]', '', phone)
    
    # Check if it's a valid Bangladeshi number
    if phone.startswith('880'):
        phone = phone[3:]  # Remove country code
    elif phone.startswith('+880'):
        phone = phone[4:]  # Remove country code with +
    
    # Should be 11 digits starting with 01
    if len(phone) == 11 and phone.startswith('01'):
        return phone
    
    return None

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login endpoint for all user types"""
    try:
        # Handle both JSON data (API) and form data (HTML form)
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        if not data:
            return error_response('Request data is required', 400)
        
        # Support both phoneNumber (frontend) and phone (legacy) and username (form)
        phone = data.get('phoneNumber') or data.get('phone') or data.get('username')
        password = data.get('password')
        
        if not phone or not password:
            if request.is_json:
                return error_response('Phone number and password are required', 400)
            else:
                flash('Phone number and password are required.', 'error')
                return redirect(url_for('templates.login'))
        
        # Validate and format phone number
        formatted_phone = validate_phone(phone)
        if not formatted_phone:
            if request.is_json:
                return error_response('Invalid phone number format', 400)
            else:
                flash('Invalid phone number format. Please enter a valid Bangladeshi number.', 'error')
                return redirect(url_for('templates.login'))
        
        # Find user by phone
        user = User.query.filter_by(phoneNumber=formatted_phone).first()
        
        if not user:
            if request.is_json:
                return error_response('Invalid phone number or password', 401)
            else:
                flash('Invalid phone number or password. Please try again.', 'error')
                return redirect(url_for('templates.login'))
        
        if not user.is_active:
            if request.is_json:
                return error_response('Account is deactivated', 401)
            else:
                flash('Account is deactivated. Please contact administrator.', 'error')
                return redirect(url_for('templates.login'))
        
        # Check if user is archived
        if user.is_archived:
            if request.is_json:
                return error_response('Account is archived and cannot log in', 401)
            else:
                flash('Your account has been archived. Please contact administrator.', 'error')
                return redirect(url_for('templates.login'))
        
        # Check password based on user role
        password_valid = False
        
        # Helper to verify hashed passwords using either werkzeug or bcrypt implementations
        def verify_hash(stored_hash, plain_password):
            # Try werkzeug first for str hashes
            try:
                if isinstance(stored_hash, str):
                    from werkzeug.security import check_password_hash as werk_check
                    try:
                        return werk_check(stored_hash, plain_password)
                    except Exception:
                        pass
            except Exception:
                pass

            # Fallback to bcrypt-based checker from utils.auth
            try:
                from utils.auth import check_password_hash as bcrypt_check
                return bool(bcrypt_check(stored_hash, plain_password))
            except Exception:
                return False

        if user.role == UserRole.STUDENT:
            # For students: Check last 4 digits of phone, legacy "student123", or hashed password
            last_4_digits = formatted_phone[-4:]  # Get last 4 digits of phone
            password_valid = (
                password == last_4_digits or  # Primary: Last 4 digits of phone
                password == "student123" or   # Legacy: Old default password
                (user.password_hash and verify_hash(user.password_hash, password))  # Hashed password
            )
        else:
            # For teachers and super users, check hashed password
            if user.password_hash:
                password_valid = verify_hash(user.password_hash, password)
        
        if not password_valid:
            # Handle error response based on request type
            if request.is_json:
                return error_response('Invalid phone number or password', 401)
            else:
                # For form submissions, redirect back to login with error
                flash('Invalid phone number or password. Please try again.', 'error')
                return redirect(url_for('templates.login'))
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Create session (match TypeScript session structure)
        session_user = {
            'id': user.id,
            'role': user.role.value,
            'name': f"{user.first_name} {user.last_name}",
            'firstName': user.first_name,
            'lastName': user.last_name,
            'phoneNumber': user.phoneNumber,
            'email': user.email or '',
            'smsCount': user.sms_count or 0,
            'batchId': None,
            'isArchived': user.is_archived or False
        }
        
        # Safely get batch ID for students
        if user.role == UserRole.STUDENT:
            try:
                user_batches = user.batches if hasattr(user, 'batches') else []
                if user_batches:
                    session_user['batchId'] = user_batches[0].id
            except Exception:
                pass  # Leave batchId as None if there's any issue
        
        # Set session data for both template and API compatibility
        session['user'] = session_user
        session['user_id'] = user.id
        session['user_role'] = user.role.value
        session.permanent = True
        
        # Prepare user data for response
        user_data = {
            'id': user.id,
            'phoneNumber': user.phoneNumber,  # Match frontend expectation
            'firstName': user.first_name,     # Match frontend expectation
            'lastName': user.last_name,       # Match frontend expectation
            'name': f"{user.first_name} {user.last_name}",  # Full name for session
            'email': user.email or '',
            'role': user.role.value,
            'profileImage': user.profile_image or '',
            'smsCount': user.sms_count or 0,
            'isArchived': user.is_archived or False,
            'lastLogin': user.last_login.isoformat() if user.last_login else None,
            'createdAt': user.created_at.isoformat() if user.created_at else None
        }
        
        # Add role-specific data
        if user.role == UserRole.STUDENT:
            # Get student's batches safely
            try:
                user_batches = user.batches if hasattr(user, 'batches') else []
                batches = [{
                    'id': batch.id,
                    'name': batch.name,
                    'description': batch.description,
                    'fee_amount': float(batch.fee_amount),
                    'is_active': batch.is_active
                } for batch in user_batches if batch.is_active]
                
                user_data['batches'] = batches
                session_user['batches'] = batches
            except Exception:
                user_data['batches'] = []
                session_user['batches'] = []
        
        # Return consistent response format
        response_data = {
            'success': True, 
            'user': session_user,
            'token': f"session_{user.id}_{user.role.value}",  # Simple token for compatibility
            'message': 'Login successful'
        }
        
        # Handle response based on request type
        # If this is a JSON request (API), return JSON response
        if request.is_json:
            final_response = {
                'success': True,
                'message': 'Login successful',
                'data': response_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            return jsonify(final_response), 200
        
        # If this is a form request (HTML), redirect to appropriate dashboard
        else:
            if user.role == UserRole.SUPER_USER:
                return redirect(url_for('templates.super_dashboard'))
            elif user.role == UserRole.TEACHER:
                return redirect(url_for('templates.teacher_dashboard'))
            elif user.role == UserRole.STUDENT:
                return redirect(url_for('templates.student_dashboard'))
            else:
                return redirect(url_for('templates.index'))
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ LOGIN ERROR: {str(e)}")  # Debug logging
        import traceback
        traceback.print_exc()  # Print full stack trace
        if request.is_json:
            return error_response(f'Login failed: {str(e)}', 500)
        else:
            flash(f'Login error: {str(e)}', 'error')
            return redirect(url_for('templates.login'))

@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Logout endpoint"""
    try:
        user_id = session.get('user_id')
        
        # Clear session
        session.clear()
        
        return success_response('Logout successful')
        
    except Exception as e:
        return error_response(f'Logout failed: {str(e)}', 500)

@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current user information"""
    try:
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', 404)
        
        user_data = {
            'id': user.id,
            'phoneNumber': user.phoneNumber,
            'firstName': user.first_name,
            'lastName': user.last_name,
            'name': f"{user.first_name} {user.last_name}",
            'email': user.email,
            'role': user.role.value,
            'profileImage': user.profile_image,
            'smsCount': user.sms_count,
            'lastLogin': user.last_login.isoformat() if user.last_login else None,
            'createdAt': user.created_at.isoformat()
        }
        
        # Add role-specific data
        if user.role == UserRole.STUDENT:
            # Get student's batches
            batches = [{
                'id': batch.id,
                'name': batch.name,
                'description': batch.description,
                'fee_amount': float(batch.fee_amount),
                'is_active': batch.is_active
            } for batch in user.batches if batch.is_active]
            
            user_data['batches'] = batches
        
        return success_response('User data retrieved', user_data)
        
    except Exception as e:
        return error_response(f'Failed to get user data: {str(e)}', 500)

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password (for teachers and super users only)"""
    try:
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        
        if not user:
            return error_response('User not found', 404)
        
        if user.role == UserRole.STUDENT:
            return error_response('Students cannot change password', 403)
        
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return error_response('Current password and new password are required', 400)
        
        # Verify current password
        if not user.password_hash or not check_password_hash(user.password_hash, current_password):
            return error_response('Current password is incorrect', 401)
        
        # Validate new password
        if len(new_password) < 6:
            return error_response('New password must be at least 6 characters long', 400)
        
        # Update password
        user.password_hash = generate_password_hash(new_password)
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return success_response('Password changed successfully')
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to change password: {str(e)}', 500)

@auth_bp.route('/session-check', methods=['GET'])
def check_session():
    """Check if user session is valid"""
    try:
        user_id = session.get('user_id')
        
        if not user_id:
            return error_response('No active session', 401)
        
        user = User.query.get(user_id)
        
        if not user or not user.is_active:
            session.clear()
            return error_response('Invalid session', 401)
        
        return success_response('Session is valid', {
            'user_id': user_id,
            'user_role': session.get('user_role'),
            'user_name': session.get('user_name')
        })
        
    except Exception as e:
        return error_response(f'Session check failed: {str(e)}', 500)