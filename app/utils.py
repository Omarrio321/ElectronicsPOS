from datetime import datetime, timedelta
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def format_currency(amount):
    """Format currency amount"""
    return f"${amount:,.2f}"

def format_datetime(dt):
    """Format datetime for display"""
    return dt.strftime('%Y-%m-%d %H:%M')

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.has_role('Admin'):
            flash('Admin access required', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    """Decorator to require manager role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.has_role('Admin') or current_user.has_role('Manager')):
            flash('Manager access required', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def generate_receipt_number():
    """Generate unique receipt number"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"REC{timestamp}"

def get_date_range(period):
    """Get date range for reports"""
    today = datetime.now().date()
    
    if period == 'today':
        start_date = today
        end_date = today
    elif period == 'yesterday':
        start_date = today - timedelta(days=1)
        end_date = start_date
    elif period == 'this_week':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif period == 'last_week':
        start_date = today - timedelta(days=today.weekday() + 7)
        end_date = start_date + timedelta(days=6)
    elif period == 'this_month':
        start_date = today.replace(day=1)
        end_date = today
    elif period == 'last_month':
        if today.month == 1:
            start_date = today.replace(year=today.year - 1, month=12, day=1)
            end_date = start_date.replace(day=31)
        else:
            start_date = today.replace(month=today.month - 1, day=1)
            end_date = today.replace(day=1) - timedelta(days=1)
    else:
        start_date = None
        end_date = None
    
    return start_date, end_date