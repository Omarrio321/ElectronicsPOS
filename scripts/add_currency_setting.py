
from app import create_app, db
from app.models import SystemSetting

app = create_app()

with app.app_context():
    currency = SystemSetting.query.filter_by(key='currency_symbol').first()
    if not currency:
        print("Creating currency_symbol setting...")
        SystemSetting.set('currency_symbol', '$', 'Currency symbol used across the system')
        print("Success: Created currency_symbol='$'.")
    else:
        print(f"Currency symbol already exists: {currency.value}")
