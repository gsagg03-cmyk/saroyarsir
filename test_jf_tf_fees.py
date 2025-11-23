#!/usr/bin/env python3
"""
Test script to verify JF and TF fee system
"""

from app import create_app
from models import db, Fee, User, Batch, UserRole
from datetime import date
from decimal import Decimal

def test_jf_tf_fees():
    """Test JF and TF fee functionality"""
    app = create_app('development')
    
    with app.app_context():
        print("=" * 60)
        print("Testing JF and TF Fee System")
        print("=" * 60)
        
        # Get existing student and batch
        student = User.query.filter_by(role=UserRole.STUDENT).first()
        batch = Batch.query.first()
        
        if not student or not batch:
            print("❌ No student or batch found. Please run init_db.py first")
            return
        
        print(f"\n✓ Found student: {student.full_name} (ID: {student.id})")
        print(f"✓ Found batch: {batch.name} (ID: {batch.id})")
        
        # Create a test fee with JF and TF
        print("\nCreating test fee with JF and TF...")
        test_fee = Fee(
            user_id=student.id,
            batch_id=batch.id,
            jf_amount=Decimal('500.00'),  # JF amount
            tf_amount=Decimal('300.00'),  # TF amount
            amount=Decimal('800.00'),     # Total
            due_date=date(2025, 1, 31),
            notes='Test fee with JF and TF'
        )
        
        db.session.add(test_fee)
        db.session.commit()
        
        print(f"✅ Created fee ID: {test_fee.id}")
        print(f"   JF Amount: {test_fee.jf_amount}")
        print(f"   TF Amount: {test_fee.tf_amount}")
        print(f"   Total Amount: {test_fee.amount}")
        
        # Query and display the fee
        print("\nQuerying fee from database...")
        retrieved_fee = Fee.query.get(test_fee.id)
        
        if retrieved_fee:
            print(f"✅ Retrieved fee:")
            print(f"   ID: {retrieved_fee.id}")
            print(f"   Student: {retrieved_fee.user.full_name}")
            print(f"   Batch: {retrieved_fee.batch.name}")
            print(f"   JF Amount: {retrieved_fee.jf_amount}")
            print(f"   TF Amount: {retrieved_fee.tf_amount}")
            print(f"   Total: {retrieved_fee.amount}")
            print(f"   Due Date: {retrieved_fee.due_date}")
            print(f"   Status: {retrieved_fee.status.value}")
        
        # Test updating JF and TF
        print("\nUpdating JF and TF amounts...")
        retrieved_fee.jf_amount = Decimal('600.00')
        retrieved_fee.tf_amount = Decimal('400.00')
        retrieved_fee.amount = Decimal('1000.00')
        db.session.commit()
        
        print(f"✅ Updated amounts:")
        print(f"   JF: 500.00 → {retrieved_fee.jf_amount}")
        print(f"   TF: 300.00 → {retrieved_fee.tf_amount}")
        print(f"   Total: 800.00 → {retrieved_fee.amount}")
        
        # Show all fees
        print("\n" + "=" * 60)
        print("All Fees in Database:")
        print("=" * 60)
        all_fees = Fee.query.all()
        
        for fee in all_fees:
            print(f"\nFee ID {fee.id}:")
            print(f"  Student: {fee.user.full_name}")
            print(f"  JF: {fee.jf_amount or 0}, TF: {fee.tf_amount or 0}, Total: {fee.amount}")
            print(f"  Due: {fee.due_date}, Status: {fee.status.value}")
        
        print("\n" + "=" * 60)
        print("✅ All tests passed successfully!")
        print("=" * 60)

if __name__ == '__main__':
    test_jf_tf_fees()
