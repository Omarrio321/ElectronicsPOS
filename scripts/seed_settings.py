from app import create_app, db
from app.models import SystemSetting

def seed_settings():
    app = create_app()
    with app.app_context():
        # Currency Settings
        currency_symbol = SystemSetting.query.filter_by(key='currency_symbol').first()
        if not currency_symbol:
            SystemSetting.set('currency_symbol', '$', 'Currency symbol used throughout the application')
            print("Added currency_symbol setting: $")
        else:
            print(f"currency_symbol already exists: {currency_symbol.value}")

        currency_code = SystemSetting.query.filter_by(key='currency_code').first()
        if not currency_code:
            SystemSetting.set('currency_code', 'USD', 'Currency ISO code (e.g. USD, EUR)')
            print("Added currency_code setting: USD")
        else:
            print(f"currency_code already exists: {currency_code.value}")
            
        # Company Settings
        company_name = SystemSetting.query.filter_by(key='company_name').first()
        if not company_name:
            SystemSetting.set('company_name', 'Electronics Store POS', 'Company Name associated with the system')
            print("Added company_name setting: Electronics Store POS")
        else:
            print(f"company_name already exists: {company_name.value}")

if __name__ == '__main__':
    seed_settings()
