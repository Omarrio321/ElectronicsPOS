"""Authorization decorators for role-based access control"""
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user


def role_required(*roles):
    """
    Decorator to restrict access to routes based on user roles.
    
    Usage:
        @role_required('Admin')
        @role_required('Admin', 'Manager')
    
    Args:
        *roles: Variable number of role names that are allowed to access the route
    
    Returns:
        Decorated function that checks user role before executing
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page', 'warning')
                return redirect(url_for('auth.login'))
            
            # Check if user has any of the required roles
            has_permission = any(current_user.has_role(role) for role in roles)
            
            if not has_permission:
                flash('You do not have permission to access this page', 'danger')
                return redirect(url_for('main.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
