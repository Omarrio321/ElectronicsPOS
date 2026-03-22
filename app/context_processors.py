from flask import g
from app.models import SystemSetting

_DEFAULTS = {
    'currency_symbol': '$',
    'company_name': 'Electronics Store POS',
    'company_address': '123 Tech Street, Hargeisa',
    'company_phone': '+252 63 444444',
    'company_logo': '',
}

def inject_global_context():
    """Inject global settings into all templates (cached per request via g)."""
    if not hasattr(g, '_system_settings'):
        try:
            g._system_settings = {k: SystemSetting.get(k, v) for k, v in _DEFAULTS.items()}
        except Exception:
            g._system_settings = dict(_DEFAULTS)
    return g._system_settings
