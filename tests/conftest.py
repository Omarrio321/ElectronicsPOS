"""
Test configuration and fixtures for POS System
Configured for MySQL database
"""
import os
import pytest
from config import TestingConfig


# Set environment variables before importing app
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-testing-only')
os.environ.setdefault('ADMIN_PASSWORD', 'test-admin-password')

from app import create_app, db
from app.models import User, Role, Product, Category, Sale, SaleItem


@pytest.fixture(scope='session')
def app():
    """Create application for testing session"""
    app = create_app(TestingConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Create test client for each test function"""
    return app.test_client()


@pytest.fixture(scope='function')
def db_session(app):
    """Create database session for each test, with cleanup after"""
    with app.app_context():
        # Clean up any existing data
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        
        yield db.session
        
        # Clean up after test
        db.session.rollback()


@pytest.fixture
def admin_role(db_session):
    """Create admin role fixture"""
    role = Role(name='Admin', description='Administrator')
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def cashier_role(db_session):
    """Create cashier role fixture"""
    role = Role(name='Cashier', description='POS Operator')
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def manager_role(db_session):
    """Create manager role fixture"""
    role = Role(name='Manager', description='Store Manager')
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def admin_user(db_session, admin_role):
    """Create admin user fixture"""
    user = User(
        username='testadmin',
        email='admin@test.com',
        role_id=admin_role.id,
        is_active=True
    )
    user.set_password('adminpass123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def cashier_user(db_session, cashier_role):
    """Create cashier user fixture"""
    user = User(
        username='testcashier',
        email='cashier@test.com',
        role_id=cashier_role.id,
        is_active=True
    )
    user.set_password('cashierpass123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def category(db_session):
    """Create product category fixture"""
    cat = Category(name='Electronics', description='Electronic devices')
    db_session.add(cat)
    db_session.commit()
    return cat


@pytest.fixture
def product(db_session, category):
    """Create product fixture"""
    prod = Product(
        name='Test Laptop',
        category_id=category.id,
        sku='LAPTOP-001',
        barcode='1234567890123',
        description='Test laptop for testing',
        cost_price=500.00,
        selling_price=799.99,
        quantity_in_stock=10,
        low_stock_threshold=5,
        is_active=True
    )
    db_session.add(prod)
    db_session.commit()
    return prod


@pytest.fixture
def authenticated_admin_client(client, admin_user):
    """Client with authenticated admin session"""
    client.post('/auth/login', data={
        'username': 'testadmin',
        'password': 'adminpass123'
    })
    return client


@pytest.fixture
def authenticated_cashier_client(client, cashier_user):
    """Client with authenticated cashier session"""
    client.post('/auth/login', data={
        'username': 'testcashier',
        'password': 'cashierpass123'
    })
    return client
