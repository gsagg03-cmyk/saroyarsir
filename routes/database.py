"""
Database Health and Verification Routes
Provides endpoints to check database status for VPS deployment
"""
from flask import Blueprint, jsonify
from models import (
    db, User, Batch, Subject, Exam, Question, QuestionOption,
    Attendance, Fee, FeePayment, Result, Message, SmsLog,
    MonthlyExam, IndividualExam, MonthlyMark, MonthlyRanking,
    SmsTemplate, Document
)
from datetime import datetime

database_bp = Blueprint('database', __name__)


@database_bp.route('/check', methods=['GET'])
def check_database():
    """
    Comprehensive database check endpoint
    Access: http://YOUR_VPS_IP:8001/api/database/check
    """
    try:
        results = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'status': 'healthy',
            'tables': {},
            'summary': {}
        }
        
        # Check each table
        tables = [
            ('users', User),
            ('batches', Batch),
            ('subjects', Subject),
            ('exams', Exam),
            ('questions', Question),
            ('question_options', QuestionOption),
            ('attendance', Attendance),
            ('fees', Fee),
            ('fee_payments', FeePayment),
            ('results', Result),
            ('messages', Message),
            ('sms_logs', SmsLog),
            ('monthly_exams', MonthlyExam),
            ('individual_exams', IndividualExam),
            ('monthly_marks', MonthlyMark),
            ('monthly_rankings', MonthlyRanking),
            ('sms_templates', SmsTemplate),
            ('documents', Document)
        ]
        
        total_records = 0
        for table_name, model in tables:
            try:
                count = model.query.count()
                total_records += count
                results['tables'][table_name] = {
                    'count': count,
                    'status': 'ok'
                }
                
                # Get sample data for some key tables
                if table_name in ['users', 'batches', 'monthly_exams', 'sms_templates']:
                    if count > 0:
                        sample = model.query.first()
                        results['tables'][table_name]['sample_id'] = sample.id
                        if hasattr(sample, 'name'):
                            results['tables'][table_name]['sample_name'] = sample.name
                        elif hasattr(sample, 'title'):
                            results['tables'][table_name]['sample_title'] = sample.title
                            
            except Exception as e:
                results['tables'][table_name] = {
                    'status': 'error',
                    'error': str(e)
                }
                results['status'] = 'partial'
        
        # Summary
        results['summary'] = {
            'total_tables': len(tables),
            'tables_ok': sum(1 for t in results['tables'].values() if t.get('status') == 'ok'),
            'total_records': total_records,
            'key_counts': {
                'users': results['tables'].get('users', {}).get('count', 0),
                'batches': results['tables'].get('batches', {}).get('count', 0),
                'students': User.query.filter_by(role='student').count() if 'users' in results['tables'] else 0,
                'teachers': User.query.filter_by(role='teacher').count() if 'users' in results['tables'] else 0,
                'monthly_exams': results['tables'].get('monthly_exams', {}).get('count', 0),
                'sms_templates': results['tables'].get('sms_templates', {}).get('count', 0),
            }
        }
        
        return jsonify(results), 200
        
    except Exception as e:
        return jsonify({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'status': 'error',
            'error': str(e)
        }), 500


@database_bp.route('/tables', methods=['GET'])
def list_tables():
    """
    List all tables with basic info
    Access: http://YOUR_VPS_IP:8001/api/database/tables
    """
    try:
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        table_info = {}
        for table in tables:
            columns = inspector.get_columns(table)
            table_info[table] = {
                'columns': [col['name'] for col in columns],
                'column_count': len(columns)
            }
        
        return jsonify({
            'success': True,
            'tables': table_info,
            'table_count': len(tables)
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@database_bp.route('/stats', methods=['GET'])
def database_stats():
    """
    Quick database statistics
    Access: http://YOUR_VPS_IP:8001/api/database/stats
    """
    try:
        stats = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'users': {
                'total': User.query.count(),
                'students': User.query.filter_by(role='student').count(),
                'teachers': User.query.filter_by(role='teacher').count(),
                'admins': User.query.filter_by(role='admin').count(),
                'active': User.query.filter_by(is_active=True).count(),
                'archived': User.query.filter_by(is_archived=True).count(),
            },
            'academic': {
                'batches': Batch.query.count(),
                'subjects': Subject.query.count(),
                'exams': Exam.query.count(),
                'monthly_exams': MonthlyExam.query.count(),
                'individual_exams': IndividualExam.query.count(),
            },
            'attendance': {
                'total_records': Attendance.query.count(),
            },
            'fees': {
                'total_fees': Fee.query.count(),
                'payments': FeePayment.query.count(),
            },
            'sms': {
                'templates': SmsTemplate.query.count(),
                'logs': SmsLog.query.count(),
            },
            'documents': {
                'total': Document.query.count(),
            }
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
