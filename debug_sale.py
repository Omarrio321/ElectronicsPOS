from app import create_app, db
from app.models import Sale, PaymentMethod
import sys
import os

# Manual config to bypass .env issues
class Config:
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:@localhost/electropos'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'dev'

app = create_app(Config)

with app.app_context():
    print(f"Connecting to: {app.config['SQLALCHEMY_DATABASE_URI']}")
    sale = Sale.query.get(82)
    if not sale:
        print("Sale 82 not found")
        sys.exit(1)
        
    print(f"Sale ID: {sale.id}")
    print(f"Payment Method (Raw): {sale.payment_method}")
    print(f"Type: {type(sale.payment_method)}")
    
    # Check if it's an enum
    if isinstance(sale.payment_method, PaymentMethod):
        print(f"Is Enum: Yes")
        print(f"Name: {sale.payment_method.name}")
        try:
            print(f"Value: {sale.payment_method.value}")
        except:
            print("Value access failed")
    else:
        print(f"Is Enum: No")
        print(f"String representation: {str(sale.payment_method)}")

    # Check Enum Definition
    print(f"Enum Member ZAAD: {PaymentMethod.ZAAD}")
    print(f"Enum Member ZAAD Value: {PaymentMethod.ZAAD.value}")
