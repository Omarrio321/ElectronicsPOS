from app.models import SystemSetting

def inject_global_context():
    """Inject global settings into all templates"""
    settings = {}
    try:
        settings['currency_symbol'] = SystemSetting.get('currency_symbol', '$')
        settings['company_name'] = SystemSetting.get('company_name', 'Electronics Store POS')
        settings['company_address'] = SystemSetting.get('company_address', '123 Tech Street, Hargeisa')
        settings['company_phone'] = SystemSetting.get('company_phone', '+252 63 444444')
        settings['company_logo'] = SystemSetting.get('company_logo', '')
    except Exception:
        settings['currency_symbol'] = '$'
        settings['company_name'] = 'Electronics Store POS'
        settings['company_address'] = '123 Tech Street, Hargeisa'
        settings['company_phone'] = '+252 63 444444'
        settings['company_logo'] = ''
    
    return settings
