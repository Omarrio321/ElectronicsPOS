import sys
import os
import unittest
from decimal import Decimal

# Add project root to path
sys.path.append(os.getcwd())

from app import create_app, db
from app.models import User, Role, Customer, CustomerLedger, LedgerEntryType, CustomerStatus

class TestCustomerBalance(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            SECRET_KEY = 'test'
            SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            WTF_CSRF_ENABLED = False
            TESTING = True

        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_debt_and_credit_calculation(self):
        print("\nTesting Debt/Credit Calculation...")
        c = Customer(full_name="Test", status=CustomerStatus.ACTIVE)
        db.session.add(c)
        db.session.commit()
        
        # 1. Initial
        self.assertEqual(c.get_outstanding_balance(), Decimal('0.00'))
        self.assertEqual(c.get_current_debt(), Decimal('0.00'))
        self.assertEqual(c.get_available_credit(), Decimal('0.00'))
        
        # 2. Add Invoice (Debt 100)
        l1 = CustomerLedger(
            customer_id=c.id, entry_type=LedgerEntryType.INVOICE,
            debit=100, credit=0, balance_after=100
        )
        db.session.add(l1)
        db.session.commit()
        
        print(f"After Invoice 100: Balance={c.get_outstanding_balance()}")
        self.assertEqual(c.get_outstanding_balance(), Decimal('100.00'))
        self.assertEqual(c.get_current_debt(), Decimal('100.00'))
        self.assertEqual(c.get_available_credit(), Decimal('0.00'))
        
        # 3. Pay 150 (Credit 50)
        l2 = CustomerLedger(
            customer_id=c.id, entry_type=LedgerEntryType.PAYMENT,
            debit=0, credit=150, balance_after=-50
        )
        db.session.add(l2)
        db.session.commit()
        
        print(f"After Payment 150: Balance={c.get_outstanding_balance()}")
        self.assertEqual(c.get_outstanding_balance(), Decimal('-50.00'))
        self.assertEqual(c.get_current_debt(), Decimal('0.00'))
        self.assertEqual(c.get_available_credit(), Decimal('50.00'))

if __name__ == '__main__':
    unittest.main()
