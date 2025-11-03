"""
Database Verification Script for VPS
Provides a comprehensive check of database tables, counts, and structure
"""
from app import create_app, db
from models import (
    User, Batch, Subject, Exam, Question, QuestionOption,
    Attendance, Fee, FeePayment, Result, Message, SmsLog,
    MonthlyExam, IndividualExam, MonthlyMark, MonthlyRanking,
    SmsTemplate, Document
)
from datetime import datetime
import json


def check_database():
    """Check database tables and return comprehensive status"""
    app = create_app()
    
    with app.app_context():
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
            
            return results
            
        except Exception as e:
            return {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'status': 'error',
                'error': str(e)
            }


if __name__ == '__main__':
    print("=" * 80)
    print("DATABASE VERIFICATION")
    print("=" * 80)
    
    results = check_database()
    
    print("\n📊 Database Status:", results['status'].upper())
    print(f"⏰ Timestamp: {results['timestamp']}")
    
    if 'summary' in results:
        print("\n📈 Summary:")
        print(f"  Total Tables: {results['summary']['total_tables']}")
        print(f"  Tables OK: {results['summary']['tables_ok']}")
        print(f"  Total Records: {results['summary']['total_records']}")
        
        print("\n👥 Key Counts:")
        for key, count in results['summary']['key_counts'].items():
            print(f"  {key}: {count}")
    
    print("\n📋 Table Details:")
    for table_name, table_info in results.get('tables', {}).items():
        status_icon = '✅' if table_info.get('status') == 'ok' else '❌'
        count = table_info.get('count', 'N/A')
        print(f"  {status_icon} {table_name}: {count} records")
        
        if table_info.get('sample_name'):
            print(f"     Sample: {table_info['sample_name']}")
        elif table_info.get('sample_title'):
            print(f"     Sample: {table_info['sample_title']}")
    
    print("\n" + "=" * 80)
    
    # Also save to JSON file
    with open('/tmp/db_check.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("✅ Results saved to /tmp/db_check.json")
    
    print("\n🌐 Access via web: http://YOUR_VPS_IP:8001/api/database/check")
    print("=" * 80)
