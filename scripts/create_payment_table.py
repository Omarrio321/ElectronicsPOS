"""
Script to create the Payment table for split payments.
Run this once to update your database schema.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models import Payment, PaymentMethod

app = create_app()

with app.app_context():
    # Create the Payment table
    db.create_all()
    print("Database tables created/updated successfully!")
    print("Payment table is now ready for split payments.")
