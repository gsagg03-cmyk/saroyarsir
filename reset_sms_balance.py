#!/usr/bin/env python3
"""
Reset SMS Balance to 0
This will reset the system SMS balance to 0 so super admin can add balance
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Settings

def reset_sms_balance():
    """Reset SMS balance to 0"""
    print("🔄 Resetting SMS Balance to 0...")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Find or create SMS balance setting
            balance_setting = Settings.query.filter_by(key='sms_balance').first()
            
            if balance_setting:
                old_balance = balance_setting.value.get('balance', 0) if balance_setting.value else 0
                balance_setting.value = {'balance': 0}
                db.session.commit()
                print(f"✅ SMS balance reset from {old_balance} to 0")
            else:
                # Create new setting with 0 balance
                balance_setting = Settings(
                    key='sms_balance',
                    value={'balance': 0},
                    category='sms',
                    description='Current SMS balance (managed by super admin)'
                )
                db.session.add(balance_setting)
                db.session.commit()
                print("✅ SMS balance initialized to 0")
            
            # Verify
            balance_setting = Settings.query.filter_by(key='sms_balance').first()
            current_balance = balance_setting.value.get('balance', 0) if balance_setting.value else 0
            print(f"\n📊 Current SMS Balance: {current_balance}")
            print("\n✨ Super admin can now add balance via Dashboard > SMS Management")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            db.session.rollback()
            return False
    
    return True

if __name__ == '__main__':
    reset_sms_balance()
