from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime, timedelta
import enum

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
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    barcode = db.Column(db.String(100), unique=True, nullable=True)
    description = db.Column(db.Text)
    cost_price = db.Column(db.Numeric(10, 2), nullable=False)
    selling_price = db.Column(db.Numeric(10, 2), nullable=False)
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
    
    def is_low_stock(self):
        return self.quantity_in_stock <= self.low_stock_threshold
    
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
    MOBILE_MONEY = "Mobile Money"

class SaleStatus(enum.Enum):
    COMPLETED = "Completed"
    REFUNDED = "Refunded"
    VOIDED = "Voided"

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    tax_rate = db.Column(db.Numeric(5, 4), nullable=False, default=0.08)
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False)
    discount = db.Column(db.Numeric(12, 2), default=0)
    grand_total = db.Column(db.Numeric(12, 2), nullable=False)
    payment_method = db.Column(db.Enum(PaymentMethod), nullable=False)
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False)
    change_given = db.Column(db.Numeric(12, 2), nullable=False)
    sale_status = db.Column(db.Enum(SaleStatus), default=SaleStatus.COMPLETED)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    sale_items = db.relationship('SaleItem', backref='sale', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Sale {self.id}>'
    
    def calculate_totals(self):
        """Calculate subtotal, tax, and total"""
        self.subtotal = sum(item.total_price for item in self.sale_items)
        self.tax_amount = self.subtotal * self.tax_rate
        self.grand_total = self.subtotal + self.tax_amount - self.discount
        return self

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity_sold = db.Column(db.Integer, nullable=False)
    unit_price_at_time = db.Column(db.Numeric(10, 2), nullable=False)
    total_price = db.Column(db.Numeric(12, 2), nullable=False)
    
    def __repr__(self):
        return f'<SaleItem {self.id}>'
    
    def calculate_total(self):
        """Calculate total price"""
        self.total_price = self.quantity_sold * self.unit_price_at_time
        return self

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
