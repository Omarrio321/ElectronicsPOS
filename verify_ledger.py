import sys
import os
from decimal import Decimal
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from app import create_app, db
from app.models import User, Role, Customer, Sale, Payment, CustomerLedger, SaleType, PaymentMethod, InvoiceStatus, LedgerEntryType, CustomerStatus, SaleItem, PriceType

def verify_ledger_credit_sync():
    app = create_app()
    with app.app_context():
        # Setup
        # Create user/role if needed (mocking mostly)
        # Using existing DB or memory? existing is safer for "real" behavior but verification uses memory typically.
        # Let's use memory to avoid polluting real DB.
        
        # ACTUALLY, I'll use the real test setup style
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        db.create_all()
        
        user = User(username='test_admin', email='test@admin.com', password_hash='abc', role_id=1)
        db.session.add(user)
        db.session.commit()
        
        cust = Customer(full_name="Credit Test", status=CustomerStatus.ACTIVE)
        db.session.add(cust)
        db.session.commit()
        
        print("\n--- Initial State ---")
        print(f"Ledger Balance: {cust.get_outstanding_balance()}")
        print(f"Credit Balance Column: {cust.credit_balance}")
        
        # 1. Sale $100
        print("\n--- Sale $100 ---")
        sale1 = Sale(
            invoice_no='INV-001', customer_id=cust.id, user_id=user.id,
            subtotal=100, tax_amount=0, grand_total=100,
            payment_method=PaymentMethod.CASH, amount_paid=0, amount_due=100,
            invoice_status=InvoiceStatus.UNPAID, change_given=0
        )
        db.session.add(sale1)
        
        # Ledger Entry for Invoice
        l1 = CustomerLedger(
            customer_id=cust.id, entry_type=LedgerEntryType.INVOICE,
            debit=100, credit=0, balance_after=100
        )
        db.session.add(l1)
        db.session.commit()
        
        print(f"Ledger Balance: {cust.get_outstanding_balance()}")
        print(f"Credit Balance Column: {cust.credit_balance}")
        
        # 2. Pay $150 (Overpay $50) via logic in receive_payment checks
        print("\n--- Pay $150 (Logic Simulation) ---")
        amount = Decimal('150')
        cur_bal = cust.get_outstanding_balance()
        new_bal = cur_bal - amount
        
        # Ledger
        l2 = CustomerLedger(
            customer_id=cust.id, entry_type=LedgerEntryType.PAYMENT,
            debit=0, credit=amount, balance_after=new_bal
        )
        db.session.add(l2)
        
        # Credit Balance Update Logic from customers.py
        # remaining_payment calculation
        # unpaid invoices = 100.
        remaining = amount - Decimal('100') # 50
        cust.credit_balance = (cust.credit_balance or 0) + remaining
        
        db.session.commit()
        
        print(f"Ledger Balance: {cust.get_outstanding_balance()} (Should be -50)")
        print(f"Credit Balance Column: {cust.credit_balance} (Should be 50)")
        
        # 3. Sale $50
        print("\n--- Sale $50 ---")
        sale2 = Sale(
            invoice_no='INV-002', customer_id=cust.id, user_id=user.id,
            subtotal=50, tax_amount=0, grand_total=50,
            payment_method=PaymentMethod.CASH, amount_paid=0, amount_due=50,
            invoice_status=InvoiceStatus.UNPAID, change_given=0
        )
        db.session.add(sale2)
        
        # Ledger Entry for Invoice
        # Logic in pos.py gets last balance (-50) and adds grand total (50)
        last_bal = cust.get_outstanding_balance()
        new_bal_sale = last_bal + 50
        l3 = CustomerLedger(
            customer_id=cust.id, entry_type=LedgerEntryType.INVOICE,
            debit=50, credit=0, balance_after=new_bal_sale
        )
        db.session.add(l3)
        
        # NOTE: pos.py DOES NOT update cust.credit_balance!
        
        db.session.commit()
        
        print(f"Ledger Balance: {cust.get_outstanding_balance()} (Should be 0)")
        print(f"Credit Balance Column: {cust.credit_balance} (Expected: 50, but logically should be 0?)")

if __name__ == "__main__":
    try:
        verify_ledger_credit_sync()
    except Exception as e:
        print(f"Error: {e}")
