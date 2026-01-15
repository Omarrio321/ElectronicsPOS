from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse, urljoin
from app.models import User
from app import db
from app.forms import LoginForm, RegistrationForm, ProfileForm

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def is_safe_url(target):
    """Check if a redirect URL is safe (relative or same domain)"""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc

from app.services.audit_service import AuditService

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user, remember=form.remember_me.data)
            
            # Log successful login
            AuditService.log_action(
                action='LOGIN',
                target_type='User',
                target_id=user.id,
                details={'username': user.username, 'status': 'Success'}
            )
            
            next_page = request.args.get('next')
            # Validate next_page to prevent open redirect attacks
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))
        else:
            # Log failed login attempt
            AuditService.log_action(
                action='LOGIN_FAILED',
                target_type='User',
                details={'username': form.username.data, 'status': 'Failed'}
            )
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    # Log logout
    AuditService.log_action(
        action='LOGOUT',
        target_type='User',
        target_id=current_user.id,
        details={'username': current_user.username}
    )
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if not current_user.has_role('Admin'):
        flash('Only administrators can register new users', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if user already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists', 'danger')
            return render_template('register.html', form=form)
        
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered', 'danger')
            return render_template('register.html', form=form)
        
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            role_id=form.role_id.data,
            is_active=True
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash('User registered successfully', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('register.html', form=form)

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        
        if form.password.data:
            current_user.set_password(form.password.data)
            
        db.session.commit()
        
        # Log profile update
        AuditService.log_action(
            action='UPDATE_PROFILE',
            target_type='User',
            target_id=current_user.id,
            details={'username': current_user.username}
        )
        
        flash('Profile updated successfully', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/profile.html', form=form)