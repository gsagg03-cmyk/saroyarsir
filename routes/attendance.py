"""
Attendance Management Routes - Enhanced for Mobile & PC Responsiveness
"""
from flask import Blueprint, request
from models import db, Attendance, User, Batch, UserRole, AttendanceStatus
from utils.auth import login_required, require_role, get_current_user
from utils.response import success_response, error_response
from datetime import datetime, timedelta
from sqlalchemy import func, and_, extract
import calendar

attendance_bp = Blueprint('attendance', __name__)

@attendance_bp.route('', methods=['GET'])
@login_required
def get_attendance():
    """Get attendance records with enhanced filtering"""
    try:
        current_user = get_current_user()
        batch_id = request.args.get('batch_id', type=int)
        date_str = request.args.get('date')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        query = Attendance.query
        
        if current_user.role == UserRole.STUDENT:
            query = query.filter(Attendance.user_id == current_user.id)
        
        if batch_id:
            query = query.filter(Attendance.batch_id == batch_id)
            
        # Filter by specific date
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                query = query.filter(Attendance.date == date_obj)
            except ValueError:
                return error_response('Invalid date format. Use YYYY-MM-DD', 400)
        
        # Filter by date range
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                query = query.filter(Attendance.date >= start_date)
            except ValueError:
                return error_response('Invalid start_date format. Use YYYY-MM-DD', 400)
                
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                query = query.filter(Attendance.date <= end_date)
            except ValueError:
                return error_response('Invalid end_date format. Use YYYY-MM-DD', 400)
        
        # Join with User and Batch tables for filtering
        query = query.join(User, Attendance.user_id == User.id).join(Batch, Attendance.batch_id == Batch.id)
        records = query.order_by(Attendance.date.desc()).all()
        
        attendance_records = []
        for record in records:
            record_data = {
                'id': record.id,
                'userId': record.user_id,
                'batchId': record.batch_id,
                'date': record.date.isoformat(),
                'status': record.status.value,
                'user': {
                    'firstName': record.user.first_name,
                    'lastName': record.user.last_name,
                    'fullName': record.user.full_name
                },
                'batch': {
                    'name': record.batch.name
                }
            }
            attendance_records.append(record_data)
        
        return success_response('Attendance retrieved', attendance_records)
        
    except Exception as e:
        return error_response(f'Failed to retrieve attendance: {str(e)}', 500)

@attendance_bp.route('/bulk', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def bulk_mark_attendance():
    """Enhanced bulk mark attendance with SMS support"""
    try:
        data = request.get_json()
        batch_id = data.get('batchId')
        attendance_date_str = data.get('date')
        attendance_data = data.get('attendanceData', [])
        send_sms = data.get('sendSms', False)
        
        if not batch_id or not attendance_date_str:
            return error_response('Batch ID and date are required', 400)
        
        attendance_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
        current_user = get_current_user()
        
        # Get batch information
        batch = Batch.query.get(batch_id)
        if not batch:
            return error_response('Batch not found', 404)
        
        attendance_updates = []
        
        for student_attendance in attendance_data:
            user_id = student_attendance.get('userId')
            status = student_attendance.get('status', 'present')
            
            if not user_id:
                continue
                
            # Validate user is in the batch
            user = User.query.get(user_id)
            if not user or batch not in user.batches:
                continue
            
            existing = Attendance.query.filter_by(
                user_id=user_id,
                batch_id=batch_id,
                date=attendance_date
            ).first()
            
            if existing:
                existing.status = AttendanceStatus(status)
                existing.marked_by = current_user.id
                existing.updated_at = datetime.utcnow()
                attendance_updates.append({
                    'student': user,
                    'status': status,
                    'action': 'updated'
                })
            else:
                new_attendance = Attendance(
                    user_id=user_id,
                    batch_id=batch_id,
                    date=attendance_date,
                    status=AttendanceStatus(status),
                    marked_by=current_user.id,
                    created_at=datetime.utcnow()
                )
                db.session.add(new_attendance)
                attendance_updates.append({
                    'student': user,
                    'status': status,
                    'action': 'created'
                })
        
        db.session.commit()
        
        # Send SMS notifications if requested
        sms_sent = 0
        sms_sent_numbers = []
        if send_sms and attendance_updates:
            # Import SMS sending function (no balance check - API handles it)
            from routes.sms import send_sms_via_api
            from models import SmsLog, SmsStatus
            
            for update in attendance_updates:
                student = update['student']
                status = update['status']
                
                # Prepare SMS message using templates
                from flask import session
                custom_templates = session.get('custom_templates', {})
                
                # Get the appropriate template based on attendance status
                if status.lower() == 'present':
                    template = custom_templates.get('attendance_present', 'Dear Parent, {student_name} was PRESENT today in {batch_name} on {date}. Keep up the good work!')
                else:  # absent
                    template = custom_templates.get('attendance_absent', 'Dear Parent, {student_name} was ABSENT today in {batch_name} on {date}. Please ensure regular attendance.')
                
                # Replace template variables with actual data
                message = template.format(
                    student_name=student.full_name,
                    batch_name=batch.name,
                    date=attendance_date.strftime('%d/%m/%Y')
                )
                
                # Collect phone numbers to send SMS
                phone_numbers = []
                
                # Add guardian/parent phone number if exists
                if hasattr(student, 'guardian_phone') and student.guardian_phone:
                    phone_numbers.append(student.guardian_phone)
                
                # Add student's own phone number
                if student.phone:
                    phone_numbers.append(student.phone)
                
                # Remove duplicates
                phone_numbers = list(set(phone_numbers))
                
                # Send SMS to each phone number
                for phone in phone_numbers:
                    if not phone:
                        continue
                    
                    # Check if teacher still has SMS balance
                    if current_user.sms_count <= 0:
                        break
                    
                    try:
                        # Send SMS
                        result = send_sms_via_api(phone, message)
                        
                        # Calculate SMS cost based on message content
                        from routes.sms import calculate_sms_cost, deduct_sms_balance
                        sms_cost = calculate_sms_cost(message) if result.get('success') else 0
                        
                        # Create SMS log
                        sms_log = SmsLog(
                            user_id=student.id,
                            phone_number=phone,
                            message=message,
                            status=SmsStatus.SENT if result.get('success') else SmsStatus.FAILED,
                            sent_by=current_user.id,
                            api_response=result,
                            cost=sms_cost,
                            sent_at=datetime.utcnow() if result.get('success') else None
                        )
                        db.session.add(sms_log)
                        
                        if result.get('success'):
                            # Deduct from local balance
                            deduct_sms_balance(sms_cost)
                            sms_sent += 1
                            sms_sent_numbers.append(phone)
                            # Deduct 1 SMS from teacher's balance
                            current_user.sms_count -= 1
                            
                    except Exception as sms_error:
                        print(f"Failed to send SMS to {phone}: {sms_error}")
            
            # Commit SMS logs and balance update
            db.session.commit()
        
        response_data = {
            'attendance_marked': len(attendance_updates),
            'sms_sent': sms_sent,
            'sms_balance': current_user.sms_count,
            'date': attendance_date.isoformat(),
            'batch_name': batch.name
        }
        
        return success_response('Attendance marked successfully', response_data)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to mark attendance: {str(e)}', 500)

@attendance_bp.route('/bulk-absent-sms', methods=['POST'])
@login_required
@require_role(UserRole.TEACHER, UserRole.SUPER_USER)
def bulk_mark_attendance_send_absent_sms():
    """Mark attendance and send SMS only to absent students"""
    try:
        data = request.get_json()
        batch_id = data.get('batchId')
        attendance_date_str = data.get('date')
        attendance_data = data.get('attendanceData', [])
        
        if not batch_id or not attendance_date_str:
            return error_response('Batch ID and date are required', 400)
        
        attendance_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
        current_user = get_current_user()
        
        # Get batch information
        batch = Batch.query.get(batch_id)
        if not batch:
            return error_response('Batch not found', 404)
        
        attendance_updates = []
        absent_students = []
        
        # Process all attendance data
        for student_attendance in attendance_data:
            user_id = student_attendance.get('userId')
            status = student_attendance.get('status', 'present')
            
            if not user_id:
                continue
                
            # Validate user is in the batch
            user = User.query.get(user_id)
            if not user or batch not in user.batches:
                continue
            
            existing = Attendance.query.filter_by(
                user_id=user_id,
                batch_id=batch_id,
                date=attendance_date
            ).first()
            
            if existing:
                existing.status = AttendanceStatus(status)
                existing.marked_by = current_user.id
                existing.updated_at = datetime.utcnow()
                attendance_updates.append({
                    'student': user,
                    'status': status,
                    'action': 'updated'
                })
            else:
                new_attendance = Attendance(
                    user_id=user_id,
                    batch_id=batch_id,
                    date=attendance_date,
                    status=AttendanceStatus(status),
                    marked_by=current_user.id,
                    created_at=datetime.utcnow()
                )
                db.session.add(new_attendance)
                attendance_updates.append({
                    'student': user,
                    'status': status,
                    'action': 'created'
                })
            
            # Collect absent students
            if status.lower() == 'absent':
                absent_students.append(user)
        
        db.session.commit()
        
        # Send SMS only to absent students
        sms_sent = 0
        sms_failed = 0
        
        if absent_students:
            # Check teacher's SMS balance
            # Import SMS sending function (no balance check - API handles it)
            from routes.sms import send_sms_via_api
            from models import SmsLog, SmsStatus
            
            for student in absent_students:
                # Get absent message template
                from flask import session
                custom_templates = session.get('custom_templates', {})
                template = custom_templates.get(
                    'attendance_absent', 
                    'Dear Parent, {student_name} was ABSENT today in {batch_name} on {date}. Please ensure regular attendance.'
                )
                
                # Replace template variables with actual data
                message = template.format(
                    student_name=student.full_name,
                    batch_name=batch.name,
                    date=attendance_date.strftime('%d/%m/%Y')
                )
                
                # Collect phone numbers to send SMS
                phone_numbers = []
                
                # Add guardian/parent phone number if exists
                if hasattr(student, 'guardian_phone') and student.guardian_phone:
                    phone_numbers.append(student.guardian_phone)
                
                # Add student's own phone number
                if student.phone:
                    phone_numbers.append(student.phone)
                
                # Remove duplicates
                phone_numbers = list(set(phone_numbers))
                
                # Send SMS to each phone number
                for phone in phone_numbers:
                    if not phone:
                        continue
                    
                    try:
                        # Send SMS
                        result = send_sms_via_api(phone, message)
                        
                        # Calculate SMS cost based on message content
                        from routes.sms import calculate_sms_cost, deduct_sms_balance
                        sms_cost = calculate_sms_cost(message) if result.get('success') else 0
                        
                        # Create SMS log
                        sms_log = SmsLog(
                            user_id=student.id,
                            phone_number=phone,
                            message=message,
                            status=SmsStatus.SENT if result.get('success') else SmsStatus.FAILED,
                            sent_by=current_user.id,
                            api_response=result,
                            cost=sms_cost,
                            sent_at=datetime.utcnow() if result.get('success') else None
                        )
                        db.session.add(sms_log)
                        
                        if result.get('success'):
                            # Deduct from local balance
                            deduct_sms_balance(sms_cost)
                            sms_sent += 1
                        else:
                            sms_failed += 1
                            
                    except Exception as sms_error:
                        print(f"Failed to send SMS to {phone}: {sms_error}")
                        sms_failed += 1
            
            # Commit SMS logs and balance update
            db.session.commit()
        
        response_data = {
            'attendance_marked': len(attendance_updates),
            'absent_count': len(absent_students),
            'sms_sent': sms_sent,
            'sms_failed': sms_failed,
            'sms_balance': current_user.sms_count,
            'date': attendance_date.isoformat(),
            'batch_name': batch.name
        }
        
        return success_response('Attendance marked and SMS sent to absent students', response_data)
        
    except Exception as e:
        db.session.rollback()
        return error_response(f'Failed to mark attendance: {str(e)}', 500)

@attendance_bp.route('/monthly', methods=['GET'])
@login_required
def get_monthly_attendance():
    """Get monthly attendance sheet data"""
    try:
        current_user = get_current_user()
        batch_id = request.args.get('batch_id', type=int)
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        
        print(f"🔍 Monthly attendance request - batch_id: {batch_id}, month: {month}, year: {year}")
        
        if not batch_id or not month or not year:
            print(f"❌ Missing parameters - batch_id: {batch_id}, month: {month}, year: {year}")
            return error_response('Batch ID, month, and year are required', 400)
        
        if current_user.role == UserRole.STUDENT:
            # Students can only view their own batch attendance
            user_batch_ids = [b.id for b in current_user.batches if b.is_active]
            if batch_id not in user_batch_ids:
                return error_response('Access denied', 403)
        
        # Get batch
        batch = Batch.query.get(batch_id)
        if not batch:
            print(f"❌ Batch not found for ID: {batch_id}")
            print(f"📋 Available batches: {[(b.id, b.name) for b in Batch.query.all()]}")
            return error_response('Batch not found', 404)
        
        print(f"✅ Found batch: {batch.name} (ID: {batch.id})")
        
        # Get students in batch
        students = User.query.join(User.batches).filter(
            User.role == UserRole.STUDENT,
            User.is_active == True,
            User.is_archived == False,
            Batch.id == batch_id
        ).order_by(User.first_name, User.last_name).all()
        
        # Get days in month
        days_in_month = calendar.monthrange(year, month)[1]
        days = list(range(1, days_in_month + 1))
        
        # Get attendance records for the month
        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, days_in_month).date()
        
        attendance_records = Attendance.query.filter(
            and_(
                Attendance.batch_id == batch_id,
                Attendance.date >= start_date,
                Attendance.date <= end_date
            )
        ).all()
        
        # Organize attendance by student and date
        attendance_map = {}
        for record in attendance_records:
            key = f"{record.user_id}_{record.date.day}"
            attendance_map[key] = record.status.value
        
        # Build response data
        students_data = []
        for student in students:
            attendance_dict = {}
            for day in days:
                key = f"{student.id}_{day}"
                attendance_dict[day] = attendance_map.get(key, None)
            
            students_data.append({
                'id': student.id,
                'name': student.full_name,
                'student_id': getattr(student, 'student_id', ''),
                'attendance': attendance_dict
            })
        
        month_data = {
            'students': students_data,
            'days': days,
            'month': month,
            'year': year,
            'month_name': calendar.month_name[month],
            'batch_name': batch.name
        }
        
        return success_response('Monthly attendance retrieved', month_data)
        
    except Exception as e:
        return error_response(f'Failed to retrieve monthly attendance: {str(e)}', 500)

@attendance_bp.route('/summary', methods=['GET'])
@login_required
def get_attendance_summary():
    """Get attendance summary for students"""
    try:
        current_user = get_current_user()
        batch_id = request.args.get('batch_id', type=int)
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        query = db.session.query(
            User.id,
            User.first_name,
            User.last_name,
            func.count(Attendance.id).label('total_days'),
            func.sum(func.case(
                (Attendance.status == AttendanceStatus.PRESENT, 1),
                else_=0
            )).label('present_days'),
            func.sum(func.case(
                (Attendance.status == AttendanceStatus.ABSENT, 1),
                else_=0
            )).label('absent_days')
        ).join(Attendance, User.id == Attendance.user_id).filter(
            User.is_active == True,
            User.is_archived == False
        )
        
        if current_user.role == UserRole.STUDENT:
            query = query.filter(User.id == current_user.id)
        
        if batch_id:
            query = query.filter(Attendance.batch_id == batch_id)
            
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(Attendance.date >= start_date)
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(Attendance.date <= end_date)
        
        results = query.group_by(User.id, User.first_name, User.last_name).all()
        
        summary_data = []
        for result in results:
            attendance_percentage = (result.present_days / result.total_days * 100) if result.total_days > 0 else 0
            
            summary_data.append({
                'student_id': result.id,
                'student_name': f"{result.first_name} {result.last_name}",
                'total_days': result.total_days,
                'present_days': result.present_days,
                'absent_days': result.absent_days,
                'attendance_percentage': round(attendance_percentage, 1)
            })
        
        return success_response('Attendance summary retrieved', summary_data)
        
    except Exception as e:
        return error_response(f'Failed to retrieve attendance summary: {str(e)}', 500)
