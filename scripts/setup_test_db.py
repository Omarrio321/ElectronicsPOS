"""Script to create test database tables"""
import os
os.environ['SECRET_KEY'] = 'test-key'
os.environ['ADMIN_PASSWORD'] = 'test-password'
os.environ['DATABASE_URL'] = 'mysql+pymysql://root:@localhost/electronics_pos_test'

from app import create_app, db
from config import TestingConfig

app = create_app(TestingConfig)
with app.app_context():
    db.create_all()
    print("Test database tables created successfully!")
