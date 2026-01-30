from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.models import User, Role, SystemSetting, Sale, Product, Category, SaleItem
from app import db
from app.forms import UserForm, SystemSettingsForm
from app.decorators import role_required
from app.services.audit_service import AuditService
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import json
import os
import uuid

# Allowed file extensions for logo upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
@role_required('Admin')
def dashboard():
    
    # Get dashboard statistics
    total_sales = Sale.query.count()
    total_revenue = db.session.query(func.sum(Sale.grand_total)).scalar() or 0
    total_products = Product.query.count()
    low_stock_products = Product.query.filter(Product.quantity_in_stock <= Product.low_stock_threshold).count()
    
    # Get today's sales
    today = datetime.utcnow().date()
    today_sales = Sale.query.filter(func.date(Sale.created_at) == today).count()
    today_revenue = db.session.query(func.sum(Sale.grand_total)).filter(
        func.date(Sale.created_at) == today
    ).scalar() or 0
    
    # Get recent sales
    recent_sales = Sale.query.order_by(desc(Sale.created_at)).limit(10).all()
    
    # Get top selling products
    top_products = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity_sold).label('total_sold')
    ).join(SaleItem).group_by(Product.id).order_by(desc('total_sold')).limit(5).all()
    
    # Get sales data for charts
    sales_data = get_sales_data()
    
    return render_template('admin/dashboard.html',
                         total_sales=total_sales,
                         total_revenue=total_revenue,
                         total_products=total_products,
                         low_stock_products=low_stock_products,
                         today_sales=today_sales,
                         today_revenue=today_revenue,
                         recent_sales=recent_sales,
                         top_products=top_products,
                         sales_data=json.dumps(sales_data))

@admin_bp.route('/users')
@login_required
@role_required('Admin')
def users():
    
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(
        page=page, per_page=10, error_out=False
    )
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def add_user():
    form = UserForm()
    form.role_id.choices = [(role.id, role.name) for role in Role.query.all()]
    
    # Password is required for new users
    from wtforms.validators import DataRequired
    form.password.validators = [DataRequired()]
    
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            role_id=form.role_id.data,
            is_active=form.is_active.data
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        try:
            db.session.commit()
            # Log user creation
            AuditService.log_action(
                action='CREATE_USER',
                target_type='User',
                target_id=user.id,
                details={'username': user.username, 'role_id': user.role_id}
            )
            flash('User created successfully', 'success')
            return redirect(url_for('admin.users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'danger')
    
    return render_template('admin/add_user.html', form=form)

@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def edit_user(user_id):
    
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    form.role_id.choices = [(role.id, role.name) for role in Role.query.all()]
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.role_id = form.role_id.data
        user.is_active = form.is_active.data
        
        if form.password.data:
            user.set_password(form.password.data)
        
        db.session.commit()
        
        # Log user update
        AuditService.log_action(
            action='UPDATE_USER',
            target_type='User',
            target_id=user.id,
            details={'username': user.username, 'role_id': user.role_id, 'is_active': user.is_active}
        )
        
        flash('User updated successfully', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/edit_user.html', form=form, user=user)

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required('Admin')
def settings():
    settings_list = SystemSetting.query.all()
    form = SystemSettingsForm()
    
    # Get current logo for display
    current_logo = SystemSetting.get('company_logo', '')
    
    if form.validate_on_submit():
        updated_keys = []
        
        # Handle logo file upload
        if 'company_logo' in request.files:
            file = request.files['company_logo']
            if file and file.filename:
                if allowed_file(file.filename):
                    # Create upload directory if it doesn't exist
                    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    # Generate unique filename to avoid overwrites
                    original_ext = file.filename.rsplit('.', 1)[1].lower()
                    unique_filename = f"company_logo_{uuid.uuid4().hex[:8]}.{original_ext}"
                    safe_filename = secure_filename(unique_filename)
                    file_path = os.path.join(upload_folder, safe_filename)
                    
                    # Delete old logo if exists
                    old_logo = SystemSetting.get('company_logo', '')
                    if old_logo:
                        old_logo_path = os.path.join(current_app.root_path, 'static', old_logo)
                        if os.path.exists(old_logo_path):
                            try:
                                os.remove(old_logo_path)
                            except OSError:
                                pass  # Ignore deletion errors
                    
                    # Save new logo
                    file.save(file_path)
                    
                    # Store relative path in database
                    relative_path = f"uploads/logos/{safe_filename}"
                    SystemSetting.set('company_logo', relative_path, 'Company logo image path')
                    updated_keys.append('company_logo')
                else:
                    flash('Invalid file type. Please upload PNG, JPG, JPEG, GIF, or WEBP.', 'danger')
        
        # Handle other settings
        for setting in settings_list:
            new_value = request.form.get(setting.key)
            if new_value is not None:
                if setting.value != new_value:
                    setting.value = new_value
                    updated_keys.append(setting.key)
        
        if updated_keys:
            db.session.commit()
            
            # Log settings update
            AuditService.log_action(
                action='UPDATE_SETTINGS',
                target_type='SystemSetting',
                details={'updated_keys': updated_keys}
            )
            flash('Settings updated successfully', 'success')
        else:
            flash('No changes detected', 'info')
            
        return redirect(url_for('admin.settings'))
    
    return render_template('admin/settings.html', settings=settings_list, form=form, current_logo=current_logo)

@admin_bp.route('/logs')
@login_required
@role_required('Admin')
def logs():
    page = request.args.get('page', 1, type=int)
    audit_logs = AuditService.get_logs(page=page, per_page=50)
    return render_template('admin/logs.html', logs=audit_logs)

def get_sales_data():
    """Get sales data for the last 30 days - optimized with single query"""
    from sqlalchemy import case
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    # Single optimized query using GROUP BY
    daily_sales = db.session.query(
        func.date(Sale.created_at).label('date'),
        func.sum(Sale.grand_total).label('total')
    ).filter(
        Sale.created_at >= start_date,
        Sale.created_at <= end_date
    ).group_by(
        func.date(Sale.created_at)
    ).all()
    
    # Convert to dictionary for fast lookup
    sales_dict = {str(row.date): float(row.total) for row in daily_sales}
    
    # Build complete date range with zeros for missing days
    sales_data = []
    current_date = start_date
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        sales_data.append({
            'date': date_str,
            'sales': sales_dict.get(date_str, 0.0)
        })
        current_date += timedelta(days=1)
    
    return sales_data
