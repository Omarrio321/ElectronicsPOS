import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.append(os.getcwd())

from app import create_app, db
from app.models import Customer, Sale, Payment, CustomerLedger, InvoiceStatus
from config import DevelopmentConfig

def inspect_customer_data(customer_id):
    app = create_app(DevelopmentConfig)
    with app.app_context():
        print(f"\n--- Inspecting Customer {customer_id} ---")
        customer = Customer.query.get(customer_id)
        if not customer:
            print("Customer not found.")
            return

        print(f"Name: {customer.full_name}")
        print(f"Current Ledger Balance: {customer.get_outstanding_balance()}")
        print(f"Current Credit Balance (Column): {customer.credit_balance}")
        
        # 1. Analyze Sales (Invoices)
        print("\n--- Sales / Invoices ---")
        sales = Sale.query.filter_by(customer_id=customer_id).all()
        total_sales_amount = Decimal('0')
        total_amount_due_sales = Decimal('0')
        
        for s in sales:
            print(f"ID: {s.id} | Inv: {s.invoice_no} | Status: {s.invoice_status.value} | Total: {s.grand_total} | Paid: {s.amount_paid} | Due: {s.amount_due}")
            total_sales_amount += s.grand_total
            total_amount_due_sales += s.amount_due
            
        print(f"Sum of Invoice Totals: {total_sales_amount}")
        print(f"Sum of Invoice Due: {total_amount_due_sales} (Should matches Unpaid Invoices count usually)")
        
        # 2. Analyze Payments
        print("\n--- Payments ---")
        payments = Payment.query.filter_by(customer_id=customer_id).all()
        total_payments_amount = Decimal('0')
        for p in payments:
            print(f"ID: {p.id} | SaleID: {p.sale_id} | Amount: {p.amount} | Method: {p.payment_method.value}")
            total_payments_amount += p.amount
            
        print(f"Sum of Payments: {total_payments_amount}")
        
        # 3. Analyze Ledger
        print("\n--- Ledger Entries ---")
        ledger = CustomerLedger.query.filter_by(customer_id=customer_id).order_by(CustomerLedger.id).all()
        running = Decimal('0')
        for l in ledger:
            print(f"ID: {l.id} | Type: {l.entry_type.value} | Deb: {l.debit} | Cred: {l.credit} | Bal After: {l.balance_after}")
            running += l.debit - l.credit
            
        print(f"Re-calculated Running Balance from Ledger Entries: {running}")
        
        # 4. Comparison
        theoretical_balance = total_sales_amount - total_payments_amount
        print("\n--- Summary ---")
        print(f"Theoretical Balance (Sales - Payments): {theoretical_balance}")
        print(f"Actual Ledger Balance: {customer.get_outstanding_balance()}")
        
        if theoretical_balance != customer.get_outstanding_balance():
            print("MISMATCH DETECTED!")
        else:
            print("Balances Match.")

if __name__ == "__main__":
    # Assuming customer ID 1 based on context/logs
    inspect_customer_data(1)
