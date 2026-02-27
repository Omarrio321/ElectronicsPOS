from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime, timedelta
import enum
from decimal import Decimal

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    users = db.relationship('User', backref='role', lazy=True)
    
    def __repr__(self):
        return f'<Role {self.name}>'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    sales = db.relationship('Sale', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_role(self, role_name):
        return self.role and self.role.name == role_name

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    products = db.relationship('Product', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'

class Product(db.Model):
    """Product with retail and wholesale pricing support"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    barcode = db.Column(db.String(100), unique=True, nullable=True)
    description = db.Column(db.Text)
    image_filename = db.Column(db.String(255), nullable=True)  # Product image file
    
    # Pricing
    cost_price = db.Column(db.Numeric(10, 2), nullable=False)
    selling_price = db.Column(db.Numeric(10, 2), nullable=False)  # Retail price
    
    # Wholesale pricing
    wholesale_price = db.Column(db.Numeric(10, 2), nullable=True)  # Wholesale price
    min_wholesale_qty = db.Column(db.Integer, default=1)  # Min qty for wholesale
    allow_wholesale = db.Column(db.Boolean, default=True)  # Can be sold wholesale
    
    # Stock
    quantity_in_stock = db.Column(db.Integer, nullable=False, default=0, index=True)
    low_stock_threshold = db.Column(db.Integer, default=10)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sale_items = db.relationship('SaleItem', backref='product', lazy=True)
    
    __table_args__ = (
        db.Index('ix_product_is_active_category', 'is_active', 'category_id'),
    )
    
    def __repr__(self):
        return f'<Product {self.name}>'
    
    @property
    def is_low_stock(self):
        """Check if product stock is at or below the low stock threshold."""
        return self.quantity_in_stock <= self.low_stock_threshold
    
    def get_price(self, price_type='RETAIL'):
        """Get price based on type (RETAIL or WHOLESALE)"""
        if price_type == 'WHOLESALE' and self.allow_wholesale and self.wholesale_price:
            return float(self.wholesale_price)
        return float(self.selling_price)
    
    def update_stock(self, quantity_change):
        """Update stock with transaction safety"""
        new_quantity = self.quantity_in_stock + quantity_change
        if new_quantity < 0:
            raise ValueError("Insufficient stock")
        self.quantity_in_stock = new_quantity
        self.updated_at = datetime.utcnow()
        return self

class PaymentMethod(enum.Enum):
    CASH = "Cash"
    CARD = "Card"
    E_DAHAB = "E-Dahab"
    ZAAD = "Zaad"
    STORE_CREDIT = "Store Credit"
    MOBILE_MONEY = "Mobile Money"  # Kept for backwards compatibility with existing sales

class SaleStatus(enum.Enum):
    COMPLETED = "Completed"
    REFUNDED = "Refunded"
    VOIDED = "Voided"


# =============================================================================
# NEW ENUMS FOR CUSTOMER + WHOLESALE + LEDGER SYSTEM
# =============================================================================

class SaleType(enum.Enum):
    """Type of sale - retail, wholesale, or mixed"""
    RETAIL = "Retail"
    WHOLESALE = "Wholesale"
    MIXED = "Mixed"


class InvoiceStatus(enum.Enum):
    """Invoice payment status"""
    PAID = "Paid"
    PARTIAL = "Partial"
    UNPAID = "Unpaid"
    VOID = "Void"


class PriceType(enum.Enum):
    """Price type for sale items"""
    RETAIL = "Retail"
    WHOLESALE = "Wholesale"


class CustomerStatus(enum.Enum):
    """Customer account status"""
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class LedgerEntryType(enum.Enum):
    """Types of ledger entries for customer balance tracking"""
    INVOICE = "Invoice"          # Debit: customer owes money
    PAYMENT = "Payment"          # Credit: customer paid money
    ADJUSTMENT = "Adjustment"    # Manual adjustment
    CREDIT_EARNED = "Credit Earned"  # Credit: future use
    CREDIT_USED = "Credit Used"      # Debit: future use


# =============================================================================
# CUSTOMER MODEL
# =============================================================================

class Customer(db.Model):
    """Customer for tracking sales, payments, and outstanding balances"""
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum(CustomerStatus), default=CustomerStatus.ACTIVE)
    
    # Credit balance stored for future use (credits system)
    credit_balance = db.Column(db.Numeric(12, 2), default=0)
    
    # Notes
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sales = db.relationship('Sale', backref='customer', lazy=True)
    payments = db.relationship('Payment', backref='customer', lazy=True)
    ledger_entries = db.relationship('CustomerLedger', backref='customer', lazy=True, order_by='CustomerLedger.created_at.desc()')
    
    def __repr__(self):
        return f'<Customer {self.id}: {self.full_name}>'
    
    def get_outstanding_balance(self):
        """Get current outstanding balance (Net) from latest ledger entry. Check db first."""
        # Ensure we flush if we are in a transaction where we just added an entry
        db.session.flush()
        latest = CustomerLedger.query.filter_by(customer_id=self.id)\
            .order_by(CustomerLedger.id.desc()).first()
            # Note: .order_by(CustomerLedger.created_at.desc(), CustomerLedger.id.desc()) might be safer
        return latest.balance_after if latest else Decimal('0.00')

    def get_current_debt(self):
        """Get positive outstanding debt (0 if credit)"""
        raw = self.get_outstanding_balance()
        return max(Decimal('0.00'), raw)

    def get_available_credit(self):
        """Get positive available credit derived from negative ledger balance"""
        raw = self.get_outstanding_balance()
        return abs(raw) if raw < 0 else Decimal('0.00')


# =============================================================================
# CUSTOMER LEDGER MODEL - SINGLE SOURCE OF TRUTH FOR BALANCES
# =============================================================================

class CustomerLedger(db.Model):
    """Ledger for tracking all customer balance changes - SINGLE SOURCE OF TRUTH"""
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False, index=True)
    
    entry_type = db.Column(db.Enum(LedgerEntryType), nullable=False)
    ref_id = db.Column(db.Integer, nullable=True)  # sale_id or payment_id
    ref_type = db.Column(db.String(50), nullable=True)  # 'Sale' or 'Payment'
    
    # Debit increases what customer owes, Credit decreases it
    debit = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    credit = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    
    # Running balance after this entry
    balance_after = db.Column(db.Numeric(12, 2), nullable=False)
    
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f'<CustomerLedger {self.id}: {self.entry_type.value} D:{self.debit} C:{self.credit}>'

class Sale(db.Model):
    """Sale/Invoice record with customer and wholesale support"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Invoice number - human-friendly unique identifier
    invoice_no = db.Column(db.String(20), unique=True, nullable=True, index=True)
    
    # Customer - nullable for guest/walk-in sales
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True, index=True)
    
    # Cashier who created this sale
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Sale type (retail/wholesale/mixed)
    sale_type = db.Column(db.Enum(SaleType), default=SaleType.RETAIL)
    
    # Financials
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    tax_rate = db.Column(db.Numeric(5, 4), nullable=False, default=0.08)
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False)
    discount = db.Column(db.Numeric(12, 2), default=0)
    grand_total = db.Column(db.Numeric(12, 2), nullable=False)
    
    # Payment tracking
    payment_method = db.Column(db.Enum(PaymentMethod), nullable=False)  # Primary method
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False)
    amount_due = db.Column(db.Numeric(12, 2), nullable=False, default=0)  # Remaining balance
    change_given = db.Column(db.Numeric(12, 2), nullable=False)
    
    # Status tracking
    sale_status = db.Column(db.Enum(SaleStatus), default=SaleStatus.COMPLETED)  # Legacy
    invoice_status = db.Column(db.Enum(InvoiceStatus), default=InvoiceStatus.PAID)  # New
    
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sale_items = db.relationship('SaleItem', backref='sale', lazy=True, cascade="all, delete-orphan")
    payments = db.relationship('Payment', backref='sale', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Sale {self.invoice_no or self.id}>'
    
    def calculate_totals(self):
        """Calculate subtotal, tax, and total"""
        self.subtotal = sum(item.total_price for item in self.sale_items)
        self.tax_amount = self.subtotal * self.tax_rate
        self.grand_total = self.subtotal + self.tax_amount - self.discount
        return self
    
    def update_payment_status(self):
        """Update invoice status based on payments"""
        total_paid = sum(p.amount for p in self.payments)
        self.amount_paid = total_paid
        self.amount_due = self.grand_total - total_paid
        
        if total_paid >= self.grand_total:
            self.invoice_status = InvoiceStatus.PAID
            self.change_given = total_paid - self.grand_total
        elif total_paid > 0:
            self.invoice_status = InvoiceStatus.PARTIAL
            self.change_given = 0
        else:
            self.invoice_status = InvoiceStatus.UNPAID
            self.change_given = 0
        return self
    
    @property
    def total_cost(self):
        """Calculate total cost of goods for this sale"""
        return sum(item.quantity_sold * item.product.cost_price for item in self.sale_items)

    @property
    def real_profit(self):
        """
        Cash-based profit calculation.
        Profit = max(0, Total Collected - Total Cost)
        No profit is recognized until the cost is covered.
        """
        collected = self.amount_paid
        cost = self.total_cost
        
        # If we haven't covered cost, profit is 0 (or negative regarding cash flow, but business rule says 0)
        if collected <= cost:
            return 0
            
        return collected - cost

    @staticmethod
    def generate_invoice_no():
        """Generate unique invoice number: INV-YYYYMMDD-XXXX"""
        today = datetime.utcnow().strftime('%Y%m%d')
        prefix = f'INV-{today}-'
        
        # Find the last invoice for today
        last = Sale.query.filter(Sale.invoice_no.like(f'{prefix}%'))\
            .order_by(Sale.invoice_no.desc()).first()
        
        if last and last.invoice_no:
            try:
                last_num = int(last.invoice_no.split('-')[-1])
                next_num = last_num + 1
            except:
                next_num = 1
        else:
            next_num = 1
        
        return f'{prefix}{next_num:04d}'

class SaleItem(db.Model):
    """Individual item in a sale with price type tracking"""
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    
    # Snapshot of product info at time of sale
    product_name = db.Column(db.String(200), nullable=True)
    product_sku = db.Column(db.String(100), nullable=True)
    
    # Pricing
    quantity_sold = db.Column(db.Integer, nullable=False)
    unit_price_at_time = db.Column(db.Numeric(10, 2), nullable=False)
    total_price = db.Column(db.Numeric(12, 2), nullable=False)
    
    # Price type (retail or wholesale)
    price_type = db.Column(db.Enum(PriceType), default=PriceType.RETAIL)
    
    def __repr__(self):
        return f'<SaleItem {self.id}: {self.product_name}>'
    
    def calculate_total(self):
        """Calculate total price"""
        self.total_price = self.quantity_sold * self.unit_price_at_time
        return self

class Payment(db.Model):
    """Individual payment record for split payment and partial payment support"""
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=True, index=True)
    
    # Customer (for payments received outside of checkout)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True, index=True)
    
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_method = db.Column(db.Enum(PaymentMethod), nullable=False)
    reference = db.Column(db.String(100), nullable=True)  # For digital payment transaction IDs
    note = db.Column(db.String(255), nullable=True)
    
    # Who recorded this payment
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to user who created payment
    created_by_user = db.relationship('User', foreign_keys=[created_by])
    
    def __repr__(self):
        return f'<Payment {self.id}: {self.payment_method.value} ${self.amount}>'

class SystemSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get(key, default=None):
        setting = SystemSetting.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set(key, value, description=None):
        setting = SystemSetting.query.filter_by(key=key).first()
        if setting:
            setting.value = value
            if description:
                setting.description = description
        else:
            setting = SystemSetting(key=key, value=value, description=description)
            db.session.add(setting)
        db.session.commit()
        return setting

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Nullable for system actions
    action = db.Column(db.String(50), nullable=False) # CREATE, UPDATE, DELETE, LOGIN, etc.
    target_type = db.Column(db.String(50)) # User, Product, Sale, etc.
    target_id = db.Column(db.String(50)) # ID of the target object
    details = db.Column(db.JSON) # Structrued details of changes
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = db.relationship('User', backref='audit_logs', lazy=True)

    def __repr__(self):
        return f'<AuditLog {self.action} on {self.target_type}>'

class ExpenseType(enum.Enum):
    MONTHLY = "Monthly (Recurring)"
    INDIVIDUAL = "Individual (One-Time)"

class ExpenseStatus(enum.Enum):
    PENDING = "Pending"
    PAID = "Paid"

class ExpenseCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    color = db.Column(db.String(20), default='#6c757d') # Hex color for badges
    is_system = db.Column(db.Boolean, default=False)
    
    # Relationships
    expenses = db.relationship('Expense', backref='category', lazy=True)

    def __repr__(self):
        return f'<ExpenseCategory {self.name}>'

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_category.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    expense_type = db.Column(db.Enum(ExpenseType), nullable=False, default=ExpenseType.INDIVIDUAL)
    status = db.Column(db.Enum(ExpenseStatus), nullable=False, default=ExpenseStatus.PENDING)
    notes = db.Column(db.Text)
    reference = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Expense {self.id}: {self.title}>'


class HeldSale(db.Model):
    """Temporarily held cart for customer who will return later"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    customer_name = db.Column(db.String(100), nullable=True)  # Optional identifier
    cart_data = db.Column(db.Text, nullable=False)  # JSON cart array
    total_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    item_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = db.relationship('User', backref='held_sales', lazy=True)
    
    def __repr__(self):
        return f'<HeldSale {self.id}: {self.customer_name or "Anonymous"}>'
