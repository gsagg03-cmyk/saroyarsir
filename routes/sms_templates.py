"""
SMS Template Management Routes
Manage SMS templates for various notifications
"""
from flask import Blueprint, request, jsonify, session
from models import db, Settings, User
from utils.auth import login_required, require_role, get_current_user
from utils.response import success_response, error_response
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

sms_templates_bp = Blueprint('sms_templates', __name__)

@sms_templates_bp.route('', methods=['GET'])
@login_required
@require_role('TEACHER', 'SUPER_USER')
def get_templates():
    """Get all SMS templates"""
    try:
        # Get templates from database (permanent storage for all teachers)
        db_templates = Settings.query.filter(
            Settings.key.like('sms_template_%')
        ).all()
        
        # Hardcoded short templates (not editable)
        hardcoded_templates = {
            'exam_result': {
                'name': 'Exam Result',
                'description': 'Short template for exam results',
                'variables': ['student_name', 'marks', 'total', 'subject', 'date'],
                'template': "{student_name} পেয়েছে {marks}/{total} ({subject}) {date}",
                'editable': False,
                'max_sms': 1
            },
            'attendance_present': {
                'name': 'Attendance Present',
                'description': 'Present notification',
                'variables': ['student_name', 'batch_name'],
                'template': "{student_name} উপস্থিত ({batch_name})",
                'editable': False,
                'max_sms': 1
            },
            'attendance_absent': {
                'name': 'Attendance Absent',
                'description': 'Absent notification',
                'variables': ['student_name', 'date', 'batch_name'],
                'template': "{student_name} অনুপস্থিত {date} ({batch_name})",
                'editable': False,
                'max_sms': 1
            },
            'fee_reminder': {
                'name': 'Fee Reminder',
                'description': 'Fee payment reminder',
                'variables': ['student_name', 'amount', 'due_date'],
                'template': "{student_name} এর ফি {amount}৳ বকেয়া। শেষ তারিখ {due_date}",
                'editable': False,
                'max_sms': 1
            }
        }
        
        # Custom templates (user can edit these - stored in database)
        templates = {
            'custom_exam': {
                'name': 'Custom Exam Message',
                'description': 'Customizable exam message',
                'variables': ['student_name', 'subject', 'marks', 'total', 'date'],
                'default': "{student_name} scored {marks}/{total} in {subject} on {date}",
                'current': '',  # Will be populated from database
                'saved': None,
                'editable': True,
                'max_sms': 2
            },
            'custom_general': {
                'name': 'Custom General Message',
                'description': 'General purpose message',
                'variables': ['student_name', 'message', 'date'],
                'default': "{student_name}: {message} ({date})",
                'current': '',  # Will be populated from database
                'saved': None,
                'editable': True,
                'max_sms': 2
            }
        }
        
        # Merge hardcoded and custom templates
        all_templates = {**hardcoded_templates, **templates}
        
        # Update with saved templates from database (for ALL editable templates)
        for db_template in db_templates:
            template_type = db_template.key.replace('sms_template_', '')
            if template_type in all_templates and all_templates[template_type].get('editable', True):
                saved_message = db_template.value.get('message', '') if db_template.value else ''
                all_templates[template_type]['saved'] = saved_message
                all_templates[template_type]['current'] = saved_message  # Show database value as current
        
        return success_response('Templates retrieved successfully', all_templates)
        
    except Exception as e:
        logger.error(f"Error getting SMS templates: {e}")
        return error_response('Failed to retrieve templates', 500)

@sms_templates_bp.route('/<template_type>', methods=['POST', 'PUT'])
@login_required
@require_role('TEACHER', 'SUPER_USER')
def update_template(template_type):
    """Update SMS template permanently in database"""
    try:
        from services.sms_service import SMSService
        
        data = request.get_json()
        
        if not data or 'message' not in data:
            return error_response('Template message is required', 400)
        
        message = data['message'].strip()
        if not message:
            return error_response('Template message cannot be empty', 400)
        
        # Check if template is editable
        # Get template info (simplified check)
        if template_type.startswith('attendance_') or template_type == 'exam_result' or template_type == 'fee_reminder':
            return error_response('This template is hardcoded and cannot be edited', 403)
        
        max_sms = data.get('max_sms', 2)
        
        # Calculate SMS count
        sms_service = SMSService()
        sms_stats = sms_service.calculate_sms_count(message)
        
        # Auto-truncate if exceeds max_sms
        if sms_stats['sms_count'] > max_sms:
            message = sms_service.truncate_message(message, max_sms)
            sms_stats = sms_service.calculate_sms_count(message)
        
        # Save to database permanently
        current_user = get_current_user()
        template_key = f"sms_template_{template_type}"
        
        # Check if template exists
        template_setting = Settings.query.filter_by(key=template_key).first()
        
        if template_setting:
            # Update existing template
            template_setting.value = {'message': message}
            template_setting.updated_by = current_user.id
            template_setting.updated_at = datetime.utcnow()
        else:
            # Create new template
            template_setting = Settings(
                key=template_key,
                value={'message': message},
                description=f"SMS template for {template_type}",
                category="sms_templates",
                updated_by=current_user.id
            )
            db.session.add(template_setting)
        
        db.session.commit()
        
        return success_response('Template saved permanently to database', {
            'template_type': template_type,
            'message': message,
            'sms_stats': sms_stats,
            'truncated': sms_stats['sms_count'] > max_sms,
            'saved_to_database': True
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating SMS template: {e}")
        return error_response('Failed to update template', 500)

@sms_templates_bp.route('/<template_type>/save', methods=['POST', 'PUT'])
@login_required
@require_role('TEACHER', 'SUPER_USER')
def save_template(template_type):
    """Save SMS template to database permanently"""
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return error_response('Template message is required', 400)
        
        message = data['message'].strip()
        if not message:
            return error_response('Template message cannot be empty', 400)
        
        current_user = get_current_user()
        template_key = f"sms_template_{template_type}"
        
        # Check if template exists
        template_setting = Settings.query.filter_by(key=template_key).first()
        
        if template_setting:
            # Update existing template
            template_setting.value = {'message': message}
            template_setting.updated_by = current_user.id
            template_setting.updated_at = datetime.utcnow()
        else:
            # Create new template
            template_setting = Settings(
                key=template_key,
                value={'message': message},
                description=f"SMS template for {template_type}",
                category="sms_templates",
                updated_by=current_user.id
            )
            db.session.add(template_setting)
        
        db.session.commit()
        
        return success_response('Template saved successfully', {
            'template_type': template_type,
            'message': message
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving SMS template: {e}")
        return error_response('Failed to save template', 500)

@sms_templates_bp.route('/<template_type>/reset', methods=['POST'])
@login_required
@require_role('TEACHER', 'SUPER_USER')
def reset_template(template_type):
    """Reset SMS template to default by removing from database"""
    try:
        # Remove from database (this resets to default for ALL teachers)
        template_key = f"sms_template_{template_type}"
        template_setting = Settings.query.filter_by(key=template_key).first()
        
        if template_setting:
            db.session.delete(template_setting)
            db.session.commit()
        
        # Get default templates
        default_templates = {
            'exam_result': "{student_name} পেয়েছে {marks}/{total} ({subject}) {date}",
            'attendance_present': "{student_name} উপস্থিত ({batch_name})",
            'attendance_absent': "{student_name} অনুপস্থিত {date} ({batch_name})",
            'fee_reminder': "{student_name} এর ফি {amount}৳ বকেয়া। শেষ তারিখ {due_date}",
            'custom_exam': "{student_name} scored {marks}/{total} in {subject} on {date}",
            'custom_general': "{student_name}: {message} ({date})"
        }
        
        default_message = default_templates.get(template_type, "Template not found")
        
        return success_response('Template reset to default for all teachers', {
            'template_type': template_type,
            'message': default_message
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting SMS template: {e}")
        return error_response('Failed to reset template', 500)

@sms_templates_bp.route('/validate-message', methods=['POST'])
@login_required
@require_role('TEACHER', 'SUPER_USER')
def validate_message():
    """Validate SMS message character count"""
    try:
        from services.sms_service import SMSService
        
        data = request.get_json()
        
        if not data or 'message' not in data:
            return error_response('Message is required', 400)
        
        message = data['message']
        
        # Calculate SMS count
        sms_service = SMSService()
        sms_stats = sms_service.calculate_sms_count(message)
        
        # For UI, we want to show a simpler format
        return success_response('Message validated', {
            'char_count': sms_stats.get('char_count', 0),
            'weighted_count': sms_stats.get('weighted_count', sms_stats.get('char_count', 0)),
            'sms_count': sms_stats.get('sms_count', 1),
            'max_characters': 100,  # Mixed Bangla/English limit
            'remaining': 100 - sms_stats.get('weighted_count', sms_stats.get('char_count', 0)),
            'is_valid': sms_stats.get('sms_count', 1) <= 1,
            'type': sms_stats.get('type', 'unknown'),
            'bangla_chars': sms_stats.get('bangla_chars', 0),
            'english_chars': sms_stats.get('english_chars', 0)
        })
        
    except Exception as e:
        logger.error(f"Error validating message: {e}")
        return error_response('Failed to validate message', 500)

@sms_templates_bp.route('/preview', methods=['POST'])
@login_required
@require_role('TEACHER', 'SUPER_USER')
def preview_template():
    """Preview SMS template with accurate SMS count calculation"""
    try:
        from services.sms_service import SMSService
        
        data = request.get_json()
        
        if not data or 'template' not in data or 'template_type' not in data:
            return error_response('Template and template type are required', 400)
        
        template = data['template']
        template_type = data['template_type']
        
        # Sample data for different template types
        sample_data = {
            'exam_result': {
                'student_name': 'আহমেদ আলী',
                'subject': 'গণিত',
                'marks': 85,
                'total': 100,
                'date': '২৩/১০/২০২৫'
            },
            'attendance_present': {
                'student_name': 'ফাতিমা খান',
                'batch_name': 'HSC-২৫'
            },
            'attendance_absent': {
                'student_name': 'রহিম উদ্দিন',
                'date': '২৩/১০',
                'batch_name': 'SSC-২৬'
            },
            'fee_reminder': {
                'student_name': 'সাকিব হোসেন',
                'amount': '২৫০০',
                'due_date': '৩০/১০'
            },
            'custom_exam': {
                'student_name': 'আয়েশা',
                'subject': 'পদার্থবিজ্ঞান',
                'marks': 92,
                'total': 100,
                'date': '২৩/১০/২০২৫'
            },
            'custom_general': {
                'student_name': 'করিম',
                'message': 'আগামীকাল ক্লাস হবে',
                'date': '২৪/১০'
            }
        }
        
        try:
            # Generate preview message
            preview_data = sample_data.get(template_type, {})
            preview_message = template.format(**preview_data)
            
            # Calculate accurate SMS count
            sms_service = SMSService()
            sms_stats = sms_service.calculate_sms_count(preview_message)
            
            return success_response('Preview generated successfully', {
                'preview': preview_message,
                'sms_stats': sms_stats,
                'sample_data': preview_data
            })
            
        except KeyError as e:
            return error_response(f'Invalid template variable: {str(e)}', 400)
        except Exception as e:
            return error_response(f'Template format error: {str(e)}', 400)
        
    except Exception as e:
        logger.error(f"Error previewing SMS template: {e}")
        return error_response('Failed to generate preview', 500)
