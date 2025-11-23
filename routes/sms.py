"""
SMS Management Routes
SMS sending, template management, and notification system
"""
from flask import Blueprint, request, jsonify, session
from models import db, SmsLog, User, Batch, UserRole, SmsStatus, user_batches
from utils.auth import login_required, require_role, get_current_user
from utils.response import success_response, error_response, paginated_response
from sqlalchemy import or_, func, extract
from datetime import datetime, date, timedelta
import requests
import os
import re

sms_bp = Blueprint('sms', __name__)

BASE_SMS_TEMPLATES = [
    {
        'id': 'attendance_present',
        'name': 'Attendance - Present',
        'category': 'attendance',
        'default_message': 'Dear Parent, {student_name} was PRESENT today in {batch_name} on {date}. Keep up the good work!',
        'variables': ['student_name', 'batch_name', 'date'],
        'editable': True
    },
    {
        'id': 'attendance_absent',
        'name': 'Attendance - Absent',
        'category': 'attendance',
        'default_message': 'Dear Parent, {student_name} was ABSENT today in {batch_name} on {date}. Please ensure regular attendance.',
        'variables': ['student_name', 'batch_name', 'date'],
        'editable': True
    },
    {
        'id': 'exam_result',
        'name': 'Exam Result',
        'category': 'exam',
        'default_message': 'Dear Parent, {student_name} scored {marks}/{total} marks in {subject} exam on {date}. Total marks: {marks}/{total}',
        'variables': ['student_name', 'subject', 'marks', 'total', 'date'],
        'editable': True
    }
]


def build_template_payload(template_def, override_message=None):
    """Create template payload with character count, applying overrides if provided."""
    message = override_message if override_message is not None else template_def['default_message']
    return {
        'id': template_def['id'],
        'name': template_def['name'],
        'category': template_def.get('category'),
        'variables': template_def.get('variables', []),
        'editable': template_def.get('editable', True),
        'message': message,
        'char_count': count_sms_characters(message)
    }


def get_template_definition(template_id):
    """Fetch static template definition by ID."""
    for template_def in BASE_SMS_TEMPLATES:
        if template_def['id'] == template_id:
            return template_def
    return None


def get_template_payload(template_id):
    """Return template payload with custom overrides applied."""
    template_def = get_template_definition(template_id)
    if not template_def:
        return None
    custom_templates = session.get('custom_templates', {})
    override = custom_templates.get(template_id)
    return build_template_payload(template_def, override)


def get_all_templates():
    """Return all templates with database and session overrides applied."""
    from models import SmsTemplate
    
    user_id = session.get('user_id')
    custom_templates = session.get('custom_templates', {})
    
    # Load saved templates from database if user is logged in
    db_templates = {}
    if user_id:
        saved_templates = SmsTemplate.query.filter_by(created_by=user_id, is_active=True).all()
        for template in saved_templates:
            db_templates[template.name] = template.content
    
    # Merge: Database templates take precedence, then session, then defaults
    return [
        build_template_payload(
            template_def, 
            custom_templates.get(template_def['id']) or db_templates.get(template_def['id'])
        )
        for template_def in BASE_SMS_TEMPLATES
    ]

def count_sms_characters(text):
    """
    Count SMS characters where Bengali characters count as 2.3x English
    Bengali Unicode ranges: 0x0980-0x09FF
    """
    bengali_count = 0
    english_count = 0
    
    for char in text:
        # Check if character is Bengali (Unicode range 0x0980-0x09FF)
        if '\u0980' <= char <= '\u09FF':
            bengali_count += 1
        else:
            english_count += 1
    
    # Total weighted character count (Bengali = 2.3x English)
    total_weighted = (bengali_count * 2.3) + english_count
    return int(total_weighted)

def calculate_sms_cost(message):
    """
    Calculate SMS cost based on message content:
    - English only (120 chars = 1 SMS)
    - Bangla only (65 chars = 1 SMS, considering 2.3x multiplier)
    - Mixed (100 chars weighted = 1 SMS)
    """
    bengali_count = 0
    english_count = 0
    
    for char in message:
        if '\u0980' <= char <= '\u09FF':
            bengali_count += 1
        else:
            english_count += 1
    
    # Determine message type
    if bengali_count == 0:
        # English only: 120 chars = 1 SMS
        sms_count = max(1, (english_count + 119) // 120)
    elif english_count == 0:
        # Bangla only: 65 chars = 1 SMS
        sms_count = max(1, (bengali_count + 64) // 65)
    else:
        # Mixed: 100 weighted chars = 1 SMS
        weighted_total = (bengali_count * 2.3) + english_count
        sms_count = max(1, int((weighted_total + 99) // 100))
    
    return sms_count

def deduct_sms_balance(sms_count):
    """Deduct SMS count from local balance in settings"""
    try:
        from models import Settings
        
        balance_setting = Settings.query.filter_by(key='sms_balance').first()
        if not balance_setting:
            # Initialize with 0 balance (super admin will add balance)
            balance_setting = Settings(
                key='sms_balance',
                value={'balance': 0},
                category='sms',
                description='Current SMS balance (managed by super admin)'
            )
            db.session.add(balance_setting)
        
        current_balance = balance_setting.value.get('balance', 0) if balance_setting.value else 0
        new_balance = max(0, current_balance - sms_count)
        
        balance_setting.value = {'balance': new_balance}
        db.session.commit()
        
        return new_balance
    except Exception as e:
        print(f"Error deducting balance: {e}")
        return 0

def validate_phone_number(phone):
    """Validate and format phone number"""
    # Remove any non-digit characters
    phone = re.sub(r'[^\d]', '', phone)
    
    # Handle country code
    if phone.startswith('880'):
        phone = phone[3:]
    elif phone.startswith('+880'):
        phone = phone[4:]
    
    # Validate Bangladesh mobile number format
    if len(phone) == 11 and phone.startswith('01'):
        return phone
    
    return None

def send_sms_via_api(phone, message):
    """Send SMS using BulkSMSBD API - Hardcoded Configuration"""
    try:
        # Hardcoded SMS API Configuration - DO NOT CHANGE
        api_key = 'gsOKLO6XtKsANCvgPHNt'
        sender_id = '8809617628909'
        api_url = 'http://bulksmsbd.net/api/smsapi'
        
        # Format phone number - remove any spaces or special characters
        formatted_phone = phone.strip().replace(' ', '').replace('-', '').replace('+', '')
        
        # Ensure phone starts with 88 for Bangladesh
        if formatted_phone.startswith('0'):
            formatted_phone = '88' + formatted_phone
        elif not formatted_phone.startswith('88'):
            formatted_phone = '88' + formatted_phone
        
        # Build URL with GET parameters
        params = {
            'api_key': api_key,
            'type': 'text',
            'number': formatted_phone,
            'senderid': sender_id,
            'message': message
        }
        
        print(f"📤 Sending SMS to {formatted_phone}...")
        print(f"🔗 URL: {api_url}")
        print(f"📋 Params: {params}")
        
        # Send SMS using GET request
        response = requests.get(api_url, params=params, timeout=30)
        
        print(f"📡 Response Status: {response.status_code}")
        print(f"📄 Response Text: {response.text}")
        
        if response.status_code == 200:
            try:
                # Parse JSON response
                response_data = response.json()
                response_code = response_data.get('response_code')
                success_message = response_data.get('success_message', '')
                error_message = response_data.get('error_message', '')
                
                print(f"📊 Response Code: {response_code}")
                
                # BulkSMSBD success codes (typically 200 or 202)
                if response_code in [200, 202]:
                    print(f"✅ SMS sent successfully to {formatted_phone}")
                    return {
                        'success': True,
                        'message_id': success_message,
                        'cost': 1
                    }
                else:
                    print(f"❌ SMS API error (code {response_code}): {error_message}")
                    return {
                        'success': False,
                        'error': error_message or f"API Error Code: {response_code}"
                    }
            except ValueError:
                # Not JSON response - treat as error
                print(f"❌ Invalid JSON response: {response.text}")
                return {
                    'success': False,
                    'error': 'Invalid API response format'
                }
        else:
            error_msg = f'HTTP {response.status_code}: {response.text}'
            print(f"❌ SMS API HTTP error: {error_msg}")
            return {'success': False, 'error': error_msg}
    
    except requests.exceptions.Timeout:
        print(f"❌ SMS API timeout for {phone}")
        return {'success': False, 'error': 'SMS API timeout'}
    except Exception as e:
        print(f"❌ SMS API exception: {str(e)}")
        return {'success': False, 'error': str(e)}
    except requests.exceptions.ConnectionError:
        return {'success': False, 'error': 'SMS API connection error'}
    except Exception as e:
        return {'success': False, 'error': f'SMS API error: {str(e)}'}

@sms_bp.route('/send', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def send_sms():
    """Send SMS to individual or multiple recipients"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data:
            return error_response('Request data is required', 400)
        
        message = data.get('message', '').strip()
        recipients = data.get('recipients', [])  # List of phone numbers
        user_ids = data.get('user_ids', [])  # List of user IDs
        
        if not message:
            return error_response('Message is required', 400)
        
        # Validate character count (Bengali = 2, English = 1, max = 130)
        char_count = count_sms_characters(message)
        if char_count > 130:
            return error_response(f'Message exceeds character limit. Current: {char_count}/130 characters', 400)
        
        # Collect phone numbers
        phone_numbers = []
        
        # Add direct phone numbers
        for phone in recipients:
            formatted_phone = validate_phone_number(phone)
            if formatted_phone:
                phone_numbers.append(formatted_phone)
        
        # Add phone numbers from user IDs
        if user_ids:
            users = User.query.filter(User.id.in_(user_ids), User.is_active == True).all()
            for user in users:
                formatted_phone = validate_phone_number(user.phone)
                if formatted_phone:
                    phone_numbers.append(formatted_phone)
        
        # Remove duplicates
        phone_numbers = list(set(phone_numbers))
        
        if not phone_numbers:
            return error_response('No valid phone numbers found', 400)
        
        # Send SMS to each recipient (no balance check - API handles it)
        sent_count = 0
        failed_count = 0
        sms_logs = []
        
        for phone in phone_numbers:
            # Create SMS log entry
            sms_log = SmsLog(
                phone_number=phone,
                message=message,
                sent_by=current_user.id,
                status=SmsStatus.PENDING
            )
            
            # Find user by phone number
            user = User.query.filter_by(phone=phone).first()
            if user:
                sms_log.user_id = user.id
            
            # Send SMS
            result = send_sms_via_api(phone, message)
            
            if result['success']:
                sms_log.status = SmsStatus.SENT
                sms_log.sent_at = datetime.utcnow()
                sms_log.api_response = result
                sms_log.cost = result.get('cost', 1)
                sent_count += 1
            else:
                sms_log.status = SmsStatus.FAILED
                sms_log.api_response = result
                failed_count += 1
            
            db.session.add(sms_log)
            sms_logs.append(sms_log)
        
        # Update user's SMS count
        current_user.sms_count -= sent_count
        
        db.session.commit()
        
        result_data = {
            'total_recipients': len(phone_numbers),
            'sent_count': sent_count,
            'failed_count': failed_count,
            'remaining_sms_balance': current_user.sms_count
        }
        
        return success_response(f'SMS sent to {sent_count} recipients', result_data)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to send SMS: {str(e)}', 500)

@sms_bp.route('/send-batch', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def send_batch_sms():
    """Send SMS to all students in specific batches"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data:
            return error_response('Request data is required', 400)
        
        message = data.get('message', '').strip()
        batch_ids = data.get('batch_ids', [])
        include_guardians = data.get('include_guardians', False)
        
        if not message:
            return error_response('Message is required', 400)
        
        # Validate character count (Bengali = 2, English = 1, max = 130)
        char_count = count_sms_characters(message)
        if char_count > 130:
            return error_response(f'Message exceeds character limit. Current: {char_count}/130 characters', 400)
        
        if not batch_ids:
            return error_response('At least one batch must be selected', 400)
        
        # Validate batches
        batches = Batch.query.filter(Batch.id.in_(batch_ids), Batch.is_active == True).all()
        if len(batches) != len(batch_ids):
            return error_response('Some batch IDs are invalid', 400)
        
        # Get all students from selected batches (exclude archived)
        students = User.query.filter(
            User.role == UserRole.STUDENT,
            User.is_active == True,
            User.is_archived == False
        ).join(user_batches).filter(user_batches.c.batch_id.in_(batch_ids)).distinct().all()
        
        # Collect phone numbers
        phone_numbers = []
        
        for student in students:
            # Add student's phone number
            formatted_phone = validate_phone_number(student.phone)
            if formatted_phone:
                phone_numbers.append(formatted_phone)
            
            # Add guardian's phone number if requested
            if include_guardians and student.guardian_phone:
                guardian_phone = validate_phone_number(student.guardian_phone)
                if guardian_phone:
                    phone_numbers.append(guardian_phone)
        
        # Remove duplicates
        phone_numbers = list(set(phone_numbers))
        
        if not phone_numbers:
            return error_response('No valid phone numbers found in selected batches', 400)
        
        # Send SMS to each recipient (no balance check - API handles it)
        sent_count = 0
        failed_count = 0
        
        for phone in phone_numbers:
            # Create SMS log entry
            sms_log = SmsLog(
                phone_number=phone,
                message=message,
                sent_by=current_user.id,
                status=SmsStatus.PENDING
            )
            
            # Find user by phone number
            user = User.query.filter_by(phone=phone).first()
            if user:
                sms_log.user_id = user.id
            
            # Send SMS
            result = send_sms_via_api(phone, message)
            
            if result['success']:
                sms_log.status = SmsStatus.SENT
                sms_log.sent_at = datetime.utcnow()
                sms_log.api_response = result
                sms_log.cost = result.get('cost', 1)
                sent_count += 1
            else:
                sms_log.status = SmsStatus.FAILED
                sms_log.api_response = result
                failed_count += 1
            
            db.session.add(sms_log)
        
        # Update user's SMS count
        current_user.sms_count -= sent_count
        
        db.session.commit()
        
        result_data = {
            'total_recipients': len(phone_numbers),
            'sent_count': sent_count,
            'failed_count': failed_count,
            'batches': [{'id': b.id, 'name': b.name} for b in batches],
            'remaining_sms_balance': current_user.sms_count
        }
        
        return success_response(f'Batch SMS sent to {sent_count} recipients', result_data)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to send batch SMS: {str(e)}', 500)

@sms_bp.route('/logs', methods=['GET'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def get_sms_logs():
    """Get SMS logs with pagination and filtering"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        status = request.args.get('status')
        phone = request.args.get('phone', '').strip()
        sent_by = request.args.get('sent_by', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        query = SmsLog.query
        
        # Filter by status
        if status and status in [s.value for s in SmsStatus]:
            query = query.filter(SmsLog.status == SmsStatus(status))
        
        # Filter by phone number
        if phone:
            query = query.filter(SmsLog.phone_number.ilike(f'%{phone}%'))
        
        # Filter by sender
        if sent_by:
            query = query.filter(SmsLog.sent_by == sent_by)
        
        # Filter by date range
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                query = query.filter(func.date(SmsLog.created_at) >= from_date)
            except ValueError:
                return error_response('Invalid date_from format. Use YYYY-MM-DD', 400)
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
                query = query.filter(func.date(SmsLog.created_at) <= to_date)
            except ValueError:
                return error_response('Invalid date_to format. Use YYYY-MM-DD', 400)
        
        # Join with sender user info
        query = query.join(User, SmsLog.sent_by == User.id, isouter=True)
        
        # Order by creation time
        query = query.order_by(SmsLog.created_at.desc())
        
        # Paginate
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        logs = []
        for log in pagination.items:
            log_data = {
                'id': log.id,
                'phone_number': log.phone_number,
                'message': log.message,
                'status': log.status.value,
                'cost': float(log.cost) if log.cost else 0,
                'sent_at': log.sent_at.isoformat() if log.sent_at else None,
                'created_at': log.created_at.isoformat(),
                'sent_by_user': {
                    'id': log.sent_by_user.id,
                    'full_name': log.sent_by_user.full_name
                } if log.sent_by_user else None
            }
            
            # Add recipient user info if available
            if log.user:
                log_data['recipient_user'] = {
                    'id': log.user.id,
                    'full_name': log.user.full_name
                }
            
            logs.append(log_data)
        
        return paginated_response(
            logs, 
            page, 
            per_page, 
            pagination.total, 
            "SMS logs retrieved successfully"
        )
        
    except Exception as e:
        return error_response(f'Failed to retrieve SMS logs: {str(e)}', 500)

@sms_bp.route('/templates', methods=['GET'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def get_sms_templates():
    """Get predefined SMS templates"""
    try:
        return jsonify(get_all_templates())
        
    except Exception as e:
        return error_response(f'Failed to get SMS templates: {str(e)}', 500)

@sms_bp.route('/templates/<template_id>', methods=['PUT'])
@login_required
def update_sms_template(template_id):
    """Update an SMS template"""
    try:
        from models import SmsTemplate
        
        data = request.get_json()
        new_message = data.get('message', '').strip()
        
        if not new_message:
            return error_response('Message is required', 400)
        
        # Validate message length
        char_count = count_sms_characters(new_message)
        if char_count > 130:
            return error_response(f'Message exceeds 130 character limit ({char_count} chars)', 400)
        
        template_def = get_template_definition(template_id)
        if not template_def:
            return error_response('Template not found', 404)
        
        user_id = session.get('user_id')
        if not user_id:
            return error_response('User not authenticated', 401)
        
        # Try to find existing template for this user and template_id
        template = SmsTemplate.query.filter_by(
            name=template_id,
            created_by=user_id
        ).first()
        
        if template:
            # Update existing template
            template.content = new_message
            template.updated_at = datetime.utcnow()
        else:
            # Create new template
            template = SmsTemplate(
                name=template_id,
                subject=template_def.get('name', template_id),
                content=new_message,
                category=template_def.get('category', 'general'),
                variables=template_def.get('variables', []),
                created_by=user_id
            )
            db.session.add(template)
        
        db.session.commit()
        
        # Also update session for immediate use
        custom_templates = session.get('custom_templates', {})
        custom_templates[template_id] = new_message
        session['custom_templates'] = custom_templates
        session.modified = True

        updated_template = build_template_payload(template_def, new_message)

        return success_response('Template updated successfully', updated_template)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to update template: {str(e)}', 500)

@sms_bp.route('/validate-message', methods=['POST'])
@login_required
def validate_sms_message():
    """Validate SMS message character count"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        if not message:
            return success_response('Message validated', {
                'char_count': 0,
                'max_characters': 130,
                'remaining': 130,
                'is_valid': True,
                'estimated_sms': 0
            })
        
        # Count characters (Bengali = 2, English = 1)
        char_count = count_sms_characters(message)
        remaining = 130 - char_count
        is_valid = char_count <= 130
        
        # Estimate number of SMS (1 SMS = 130 chars)
        estimated_sms = (char_count // 130) + (1 if char_count % 130 > 0 else 0)
        
        return success_response('Message validated', {
            'char_count': char_count,
            'max_characters': 130,
            'remaining': remaining,
            'is_valid': is_valid,
            'estimated_sms': estimated_sms,
            'message_length': len(message)
        })
        
    except Exception as e:
        return error_response(f'Failed to validate message: {str(e)}', 500)

@sms_bp.route('/balance', methods=['GET'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def get_sms_balance():
    """Get SMS balance from local settings"""
    try:
        from models import Settings
        
        # Get balance from settings
        balance_setting = Settings.query.filter_by(key='sms_balance').first()
        if not balance_setting:
            # Initialize with 0 balance (super admin will add balance)
            balance_setting = Settings(
                key='sms_balance',
                value={'balance': 0},
                category='sms',
                description='Current SMS balance (managed by super admin)'
            )
            db.session.add(balance_setting)
            db.session.commit()
        
        balance = balance_setting.value.get('balance', 0) if balance_setting.value else 0
        
        current_user = get_current_user()
        total_sent = SmsLog.query.filter(
            SmsLog.sent_by == current_user.id,
            SmsLog.status == SmsStatus.SENT
        ).count()

        current_month = datetime.now().month
        sent_this_month = SmsLog.query.filter(
            SmsLog.sent_by == current_user.id,
            SmsLog.status == SmsStatus.SENT,
            func.extract('month', SmsLog.sent_at) == current_month
        ).count()

        return success_response('SMS balance retrieved', {
            'balance': balance,
            'total_sent': total_sent,
            'sent_this_month': sent_this_month
        })

    except Exception as e:
        return error_response(f'Failed to get SMS balance: {str(e)}', 500)


@sms_bp.route('/balance-check', methods=['GET'])
def get_sms_balance_noauth():
    """Get SMS balance from local settings (no auth required)"""
    try:
        from models import Settings
        
        # Get balance from settings
        balance_setting = Settings.query.filter_by(key='sms_balance').first()
        if not balance_setting:
            # Initialize with 0 balance (super admin will add balance)
            balance_setting = Settings(
                key='sms_balance',
                value={'balance': 0},
                category='sms',
                description='Current SMS balance (managed by super admin)'
            )
            db.session.add(balance_setting)
            db.session.commit()
        
        balance = balance_setting.value.get('balance', 0) if balance_setting.value else 0

        # Get Sample Teacher for stats
        teacher = User.query.filter_by(first_name='Sample', last_name='Teacher', role=UserRole.TEACHER).first()
        
        total_sent = 0
        if teacher:
            total_sent = SmsLog.query.filter(
                SmsLog.sent_by == teacher.id,
                SmsLog.status == SmsStatus.SENT
            ).count()

        return success_response('SMS balance retrieved', {
            'balance': balance,
            'total_sent': total_sent,
            'teacher_name': teacher.full_name if teacher else 'N/A',
            'teacher_phone': teacher.phone if teacher else 'N/A'
        })

    except Exception as e:
        return error_response(f'Failed to get SMS balance: {str(e)}', 500)


@sms_bp.route('/balance/add', methods=['POST'])
@login_required
@require_role(UserRole.SUPER_USER)
def add_sms_balance():
    """Add SMS balance to system-wide balance (Super user only)"""
    try:
        from models import Settings
        
        data = request.get_json()
        amount = data.get('amount')

        if amount is None:
            return error_response('Amount is required', 400)

        try:
            amount = int(amount)
        except (TypeError, ValueError):
            return error_response('Amount must be an integer', 400)

        if amount <= 0:
            return error_response('Amount must be a positive integer', 400)

        # Get or create SMS balance setting
        balance_setting = Settings.query.filter_by(key='sms_balance').first()
        if not balance_setting:
            balance_setting = Settings(
                key='sms_balance',
                value={'balance': 0},
                category='sms',
                description='Current SMS balance (managed by super admin)'
            )
            db.session.add(balance_setting)
        
        # Add to current balance
        current_balance = balance_setting.value.get('balance', 0) if balance_setting.value else 0
        new_balance = current_balance + amount
        
        balance_setting.value = {'balance': new_balance}
        db.session.commit()

        current_user = get_current_user()
        return success_response('SMS balance added successfully', {
            'previous_balance': current_balance,
            'added_amount': amount,
            'new_balance': new_balance,
            'updated_by': current_user.full_name
        })

    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to add SMS balance: {str(e)}', 500)

@sms_bp.route('/statistics', methods=['GET'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def get_sms_statistics():
    """Get SMS usage statistics"""
    try:
        # Get date range
        days = request.args.get('days', 30, type=int)
        start_date = datetime.now() - timedelta(days=days)
        
        # Basic statistics
        total_sent = SmsLog.query.filter(
            SmsLog.status == SmsStatus.SENT,
            SmsLog.sent_at >= start_date
        ).count()
        
        total_failed = SmsLog.query.filter(
            SmsLog.status == SmsStatus.FAILED,
            SmsLog.created_at >= start_date
        ).count()
        
        # Success rate
        total_attempts = total_sent + total_failed
        success_rate = (total_sent / total_attempts * 100) if total_attempts > 0 else 0
        
        # Daily statistics
        daily_stats = db.session.query(
            func.date(SmsLog.sent_at).label('date'),
            func.count(SmsLog.id).label('count')
        ).filter(
            SmsLog.status == SmsStatus.SENT,
            SmsLog.sent_at >= start_date
        ).group_by(func.date(SmsLog.sent_at)).order_by('date').all()
        
        daily_data = [{'date': stat.date.isoformat(), 'count': stat.count} for stat in daily_stats]
        
        # Top senders
        top_senders = db.session.query(
            User.full_name,
            func.count(SmsLog.id).label('count')
        ).join(SmsLog, User.id == SmsLog.sent_by).filter(
            SmsLog.status == SmsStatus.SENT,
            SmsLog.sent_at >= start_date
        ).group_by(User.id, User.full_name).order_by(func.count(SmsLog.id).desc()).limit(5).all()
        
        top_senders_data = [{'name': sender.full_name, 'count': sender.count} for sender in top_senders]
        
        statistics = {
            'period_days': days,
            'total_sent': total_sent,
            'total_failed': total_failed,
            'success_rate': round(success_rate, 2),
            'daily_stats': daily_data,
            'top_senders': top_senders_data
        }
        
        return success_response('SMS statistics retrieved', {'statistics': statistics})
        
    except Exception as e:
        return error_response(f'Failed to get SMS statistics: {str(e)}', 500)

@sms_bp.route('/add-credits', methods=['POST'])
@login_required
@require_role(UserRole.SUPER_USER)
def add_sms_credits():
    """Add SMS credits to a teacher (Super Admin only)"""
    try:
        data = request.get_json()
        teacher_id = data.get('teacher_id')
        credits = data.get('credits')
        memo = data.get('memo', 'Credits added by Super Admin')
        
        if not teacher_id or credits is None:
            return error_response('Teacher ID and credits are required', 400)
        
        if not isinstance(credits, int) or credits == 0:
            return error_response('Credits must be a non-zero integer', 400)
            
        if credits > 10000:
            return error_response('Cannot add more than 10,000 credits at once', 400)
        
        if credits < -10000:
            return error_response('Cannot reduce more than 10,000 credits at once', 400)
        
        # Get teacher
        teacher = User.query.filter_by(id=teacher_id, role=UserRole.TEACHER, is_active=True).first()
        if not teacher:
            return error_response('Teacher not found', 404)
        
        # Add or reduce credits
        old_balance = teacher.sms_count or 0
        new_balance = old_balance + credits
        
        # Prevent negative balance
        if new_balance < 0:
            return error_response(f'Cannot reduce credits. Teacher has {old_balance} credits, cannot reduce by {abs(credits)}', 400)
        
        teacher.sms_count = new_balance
        teacher.updated_at = datetime.utcnow()
        
        # Log the transaction
        current_user = get_current_user()
        
        # Determine action type
        action_type = 'Added' if credits > 0 else 'Reduced'
        
        # Create SMS log for audit (using correct field names)
        sms_log = SmsLog(
            user_id=teacher.id,
            phone_number=teacher.phone,
            message=f"SMS Credits {action_type}: {abs(credits)} credits. New balance: {teacher.sms_count}. Memo: {memo}",
            status=SmsStatus.SENT,
            sent_by=current_user.id,
            api_response={'type': 'credit_adjustment', 'action': action_type.lower(), 'added_by': f"{current_user.first_name} {current_user.last_name}", 'memo': memo},
            cost=0,
            sent_at=datetime.utcnow()
        )
        
        db.session.add(sms_log)
        db.session.commit()
        
        return success_response(f'Successfully {action_type.lower()} {abs(credits)} SMS credits for {teacher.first_name} {teacher.last_name}', {
            'teacher_id': teacher.id,
            'teacher_name': f"{teacher.first_name} {teacher.last_name}",
            'credits_adjusted': credits,
            'action': action_type.lower(),
            'old_balance': old_balance,
            'new_balance': teacher.sms_count,
            'memo': memo
        })
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to add SMS credits: {str(e)}', 500)

@sms_bp.route('/stats', methods=['GET'])
@login_required
@require_role(UserRole.SUPER_USER)
def get_sms_system_stats():
    """Get SMS system statistics (Super Admin only)"""
    try:
        # Get all teachers with their SMS counts
        teachers = User.query.filter_by(role=UserRole.TEACHER, is_active=True).all()
        
        total_credits_distributed = sum(teacher.sms_count or 0 for teacher in teachers)
        active_teachers = len([t for t in teachers if (t.sms_count or 0) > 0])
        
        # Get total SMS sent (approximation of credits used)
        total_sent = SmsLog.query.filter_by(status=SmsStatus.SENT).count()
        
        stats = {
            'totalCreditsDistributed': total_credits_distributed,
            'totalCreditsUsed': total_sent,  # Approximation
            'activeTeachers': active_teachers,
            'totalTeachers': len(teachers)
        }
        
        return success_response('SMS system statistics retrieved', stats)
        
    except Exception as e:
        return error_response(f'Failed to get SMS system statistics: {str(e)}', 500)

@sms_bp.route('/send-bulk', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def send_bulk_sms():
    """Send SMS to multiple recipients (batch or individual students)"""
    try:
        current_user = get_current_user()
        data = request.get_json()
        
        if not data:
            return error_response('Request data is required', 400)
        
        template_id = data.get('template_id')
        batch_id = data.get('batch_id')
        recipient_type = data.get('recipient_type', 'all')  # 'all' or 'individual'
        student_ids = data.get('student_ids', [])
        use_custom_message = data.get('use_custom_message', False)
        custom_message = (data.get('custom_message') or '').strip()

        if not batch_id:
            return error_response('Batch ID is required', 400)

        if student_ids:
            try:
                student_ids = [int(s) for s in student_ids]
            except (TypeError, ValueError):
                return error_response('Invalid student IDs provided', 400)

        if use_custom_message:
            if not custom_message:
                return error_response('Custom message is required', 400)
            base_message = custom_message
        else:
            if not template_id:
                return error_response('Template ID is required', 400)
            template_payload = get_template_payload(template_id)
            if not template_payload:
                return error_response('SMS template not found', 404)
            base_message = template_payload['message']

        char_count = count_sms_characters(base_message)
        if char_count > 130:
            return error_response(f'Message exceeds 130 character limit ({char_count} chars)', 400)

        # Get the batch and verify access
        batch = Batch.query.get(batch_id)
        if not batch:
            return error_response('Batch not found', 404)

        if current_user.role == UserRole.TEACHER and batch not in current_user.batches:
            return error_response('You do not have access to this batch', 403)

        # Determine recipients based on selection type
        if recipient_type == 'all':
            recipients = [student for student in batch.students if student.is_active]
        elif recipient_type == 'individual':
            if not student_ids:
                return error_response('Student IDs are required for individual selection', 400)
            recipients = [student for student in batch.students if student.is_active and student.id in student_ids]
        else:
            return error_response('Invalid recipient type. Use "all" or "individual"', 400)

        if not recipients:
            return error_response('No valid recipients found', 400)

        valid_recipients = []
        invalid_recipients = []
        for student in recipients:
            phone = validate_phone_number(student.phoneNumber or '')
            if phone:
                valid_recipients.append((student, phone))
            else:
                invalid_recipients.append(student.full_name)

        if not valid_recipients:
            return error_response('No recipients have valid phone numbers', 400)

        # Send SMS to each recipient (no balance check - API handles it)
        sent_count = 0
        failed_count = 0
        failed_recipients = []

        for student, phone in valid_recipients:
            try:
                message_to_send = base_message
                message_to_send = message_to_send.replace('{student_name}', (student.first_name or ''))
                message_to_send = message_to_send.replace('{batch_name}', batch.name or '')
                message_to_send = message_to_send.replace('{date}', datetime.now().strftime('%d/%m/%Y'))
                message_to_send = message_to_send.replace('{total}', str(getattr(student, 'total_marks', '')))
                message_to_send = message_to_send.replace('{marks}', str(getattr(student, 'obtained_marks', '')))
                message_to_send = message_to_send.replace('{subject}', getattr(student, 'subject', ''))

                sms_response = send_sms_via_api(phone, message_to_send)

                if sms_response.get('success'):
                    # Calculate SMS cost based on message content
                    sms_cost = calculate_sms_cost(message_to_send)
                    
                    sms_log = SmsLog(
                        user_id=student.id,
                        phone_number=phone,
                        message=message_to_send,
                        status=SmsStatus.SENT,
                        api_response=sms_response,
                        sent_by=current_user.id,
                        cost=sms_cost,
                        sent_at=datetime.utcnow()
                    )
                    db.session.add(sms_log)
                    
                    # Deduct from local balance
                    deduct_sms_balance(sms_cost)
                    sent_count += 1
                else:
                    sms_log = SmsLog(
                        user_id=student.id,
                        phone_number=phone,
                        message=message_to_send,
                        status=SmsStatus.FAILED,
                        api_response=sms_response,
                        sent_by=current_user.id,
                        cost=0,
                        sent_at=datetime.utcnow()
                    )
                    db.session.add(sms_log)
                    failed_count += 1
                    failed_recipients.append(student.full_name)

            except Exception as e:
                sms_log = SmsLog(
                    user_id=student.id,
                    phone_number=phone,
                    message=base_message,
                    status=SmsStatus.FAILED,
                    api_response={'error': str(e)},
                    sent_by=current_user.id,
                    cost=0,
                    sent_at=datetime.utcnow()
                )
                db.session.add(sms_log)
                failed_count += 1
                failed_recipients.append(student.full_name)

        if invalid_recipients:
            failed_recipients.extend([f'{name} (invalid phone)' for name in invalid_recipients])

        db.session.commit()

        response_data = {
            'sent': sent_count,
            'failed': failed_count,
            'total_recipients': len(valid_recipients),
            'remaining_balance': current_user.sms_count or 0,
            'failed_recipients': failed_recipients or None,
            'invalid_contacts': invalid_recipients or None,
            'used_custom_message': use_custom_message
        }

        if sent_count > 0 and failed_count == 0:
            message_text = f'Successfully sent SMS to all {sent_count} recipients'
        elif sent_count > 0 and failed_count > 0:
            message_text = f'Sent SMS to {sent_count} recipients, {failed_count} failed'
        else:
            message_text = f'Failed to send SMS to all {failed_count} recipients'

        return success_response(message_text, response_data)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to send bulk SMS: {str(e)}', 500)


@sms_bp.route('/send-bulk-noauth', methods=['POST'])
def send_bulk_sms_noauth():
    """Send SMS to multiple recipients without auth (for debugging)"""
    try:
        # Get Sample Teacher
        current_user = User.query.filter_by(first_name='Sample', last_name='Teacher', role=UserRole.TEACHER).first()
        if not current_user:
            return error_response('Sample Teacher not found', 404)
            
        data = request.get_json()
        
        if not data:
            return error_response('Request data is required', 400)
        
        template_id = data.get('template_id')
        batch_id = data.get('batch_id')
        recipient_type = data.get('recipient_type', 'all')
        student_ids = data.get('student_ids', [])
        use_custom_message = data.get('use_custom_message', False)
        custom_message = (data.get('custom_message') or '').strip()

        if not batch_id:
            return error_response('Batch ID is required', 400)

        if student_ids:
            try:
                student_ids = [int(s) for s in student_ids]
            except (TypeError, ValueError):
                return error_response('Invalid student IDs provided', 400)

        if use_custom_message:
            if not custom_message:
                return error_response('Custom message is required', 400)
            base_message = custom_message
        else:
            if not template_id:
                return error_response('Template ID is required', 400)
            template_payload = get_template_payload(template_id)
            if not template_payload:
                return error_response('SMS template not found', 404)
            base_message = template_payload['message']

        char_count = count_sms_characters(base_message)
        if char_count > 130:
            return error_response(f'Message exceeds 130 character limit ({char_count} chars)', 400)

        batch = Batch.query.get(batch_id)
        if not batch:
            return error_response('Batch not found', 404)

        if recipient_type == 'all':
            recipients = [student for student in batch.students if student.is_active]
        elif recipient_type == 'individual':
            if not student_ids:
                return error_response('Student IDs are required for individual selection', 400)
            recipients = [student for student in batch.students if student.is_active and student.id in student_ids]
        else:
            return error_response('Invalid recipient type', 400)

        if not recipients:
            return error_response('No valid recipients found', 400)

        valid_recipients = []
        for student in recipients:
            phone = validate_phone_number(student.phoneNumber or '')
            if phone:
                valid_recipients.append((student, phone))

        if not valid_recipients:
            return error_response('No recipients have valid phone numbers', 400)

        # Send SMS to each recipient (no balance check - API handles it)
        sent_count = 0
        failed_count = 0

        for student, phone in valid_recipients:
            try:
                message_to_send = base_message
                message_to_send = message_to_send.replace('{student_name}', (student.first_name or ''))
                message_to_send = message_to_send.replace('{batch_name}', batch.name or '')
                message_to_send = message_to_send.replace('{date}', datetime.now().strftime('%d/%m/%Y'))

                sms_response = send_sms_via_api(phone, message_to_send)

                if sms_response.get('success'):
                    # Calculate SMS cost based on message content
                    sms_cost = calculate_sms_cost(message_to_send)
                    
                    sms_log = SmsLog(
                        user_id=student.id,
                        phone_number=phone,
                        message=message_to_send,
                        status=SmsStatus.SENT,
                        api_response=sms_response,
                        sent_by=current_user.id,
                        cost=sms_cost,
                        sent_at=datetime.utcnow()
                    )
                    db.session.add(sms_log)
                    
                    # Deduct from local balance
                    deduct_sms_balance(sms_cost)
                    sent_count += 1
                else:
                    sms_log = SmsLog(
                        user_id=student.id,
                        phone_number=phone,
                        message=message_to_send,
                        status=SmsStatus.FAILED,
                        api_response=sms_response,
                        sent_by=current_user.id,
                        cost=0,
                        sent_at=datetime.utcnow()
                    )
                    db.session.add(sms_log)
                    failed_count += 1
            except Exception as e:
                failed_count += 1

        db.session.commit()

        response_data = {
            'sent': sent_count,
            'failed': failed_count,
            'total_recipients': len(valid_recipients),
            'remaining_balance': current_user.sms_count or 0,
        }

        return success_response(f'SMS sent to {sent_count} recipients', response_data)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to send bulk SMS: {str(e)}', 500)