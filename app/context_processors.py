from app.models import SystemSetting

def inject_global_context():
    """Inject global settings into all templates"""
    settings = {}
    try:
        settings['currency_symbol'] = SystemSetting.get('currency_symbol', '$')
        settings['company_name'] = SystemSetting.get('company_name', 'Electronics Store POS')
    except Exception:
        settings['currency_symbol'] = '$'
        settings['company_name'] = 'Electronics Store POS'
    
    return settings
