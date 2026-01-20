from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Product, Category, SaleItem
from app import db
from app.forms import ProductForm
from app.services.audit_service import AuditService
from sqlalchemy import or_, desc
import json
import pdfkit
from io import BytesIO
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime
from flask import send_file, Response, current_app
from app.models import SystemSetting
from app.utils import format_currency


products_bp = Blueprint('products', __name__, url_prefix='/products')

@products_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    category_id = request.args.get('category_id', type=int)
    
    query = Product.query
    
    if search:
        query = query.filter(or_(
            Product.name.contains(search),
            Product.sku.contains(search),
            Product.barcode.contains(search)
        ))
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    products = query.order_by(desc(Product.created_at)).paginate(
        page=page, per_page=10, error_out=False
    )
    
    categories = Category.query.all()
    
    return render_template('products/index.html', 
                         products=products, 
                         categories=categories,
                         search=search,
                         category_id=category_id)

@products_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('products.index'))
    
    form = ProductForm()
    form.category_id.choices = [(c.id, c.name) for c in Category.query.all()]
    
    if form.validate_on_submit():
        product = Product(
            name=form.name.data,
            category_id=form.category_id.data,
            sku=form.sku.data,
            barcode=form.barcode.data,
            cost_price=form.cost_price.data,
            selling_price=form.selling_price.data,
            quantity_in_stock=form.quantity.data,
            low_stock_threshold=form.low_stock_threshold.data,
            description=form.description.data
        )
        db.session.add(product)
        db.session.commit()
        
        # Log product creation
        AuditService.log_action(
            action='CREATE_PRODUCT',
            target_type='Product',
            target_id=product.id,
            details={'name': product.name, 'sku': product.sku}
        )
        
        flash('Product added successfully', 'success')
        return redirect(url_for('products.index'))
    
    return render_template('products/add.html', form=form)

@products_bp.route('/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(product_id):
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('products.index'))
    
    product = Product.query.get_or_404(product_id)
    form = ProductForm(obj=product)
    
    # Manually populate quantity field because names mismatch (form.quantity vs model.quantity_in_stock)
    if request.method == 'GET':
        form.quantity.data = product.quantity_in_stock
        
    form.category_id.choices = [(c.id, c.name) for c in Category.query.all()]
    
    if form.validate_on_submit():
        product.name = form.name.data
        product.category_id = form.category_id.data
        product.sku = form.sku.data
        product.barcode = form.barcode.data
        product.cost_price = form.cost_price.data
        product.selling_price = form.selling_price.data
        product.quantity_in_stock = form.quantity.data
        product.low_stock_threshold = form.low_stock_threshold.data
        product.description = form.description.data
        
        db.session.commit()
        
        # Log product update
        AuditService.log_action(
            action='UPDATE_PRODUCT',
            target_type='Product',
            target_id=product.id,
            details={'name': product.name, 'sku': product.sku}
        )
        
        flash('Product updated successfully', 'success')
        return redirect(url_for('products.index'))
    
    return render_template('products/edit.html', form=form, product=product)

@products_bp.route('/<int:product_id>/delete', methods=['POST'])
@login_required
def delete(product_id):
    if not current_user.has_role('Admin'):
        flash('Access denied', 'danger')
        return redirect(url_for('products.index'))
    
    product = Product.query.get_or_404(product_id)
    
    # Check if product has sales
    if SaleItem.query.filter_by(product_id=product_id).first():
        flash('Cannot delete product with existing sales', 'danger')
        return redirect(url_for('products.index'))
    
    db.session.delete(product)
    db.session.commit()
    
    # Log product deletion
    AuditService.log_action(
        action='DELETE_PRODUCT',
        target_type='Product',
        target_id=product.id,
        details={'name': product.name, 'sku': product.sku}
    )
    
    flash('Product deleted successfully', 'success')
    return redirect(url_for('products.index'))

@products_bp.route('/search')
@login_required
def search():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    products = Product.query.filter(
        or_(
            Product.name.contains(query),
            Product.sku.contains(query),
            Product.barcode.contains(query)
        )
    ).limit(10).all()
    
    results = []
    for product in products:
        results.append({
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'barcode': product.barcode,
            'price': float(product.selling_price),
            'quantity': product.quantity_in_stock,
            'category': product.category.name if product.category else ''
        })
    
    return jsonify(results)

@products_bp.route('/low-stock')
@login_required
def low_stock():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('products.index'))
    
    products = Product.query.filter(Product.quantity_in_stock <= Product.low_stock_threshold).all()
    return render_template('products/low_stock.html', products=products)

@products_bp.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('products.index'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if Category.query.filter_by(name=name).first():
            flash('Category with this name already exists.', 'warning')
        else:
            try:
                category = Category(name=name, description=description)
                db.session.add(category)
                db.session.commit()
                
                AuditService.log_action(
                    action='CREATE_CATEGORY',
                    target_type='Category',
                    target_id=category.id,
                    details={'name': category.name}
                )
                flash('Category added successfully.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error adding category: {str(e)}', 'danger')
        return redirect(url_for('products.categories'))

    categories = Category.query.order_by(Category.name).all()
    return render_template('products/categories.html', categories=categories)

@products_bp.route('/categories/<int:id>/edit', methods=['POST'])
@login_required
def edit_category(id):
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('products.index'))

    category = Category.query.get_or_404(id)
    try:
        category.name = request.form.get('name')
        category.description = request.form.get('description')
        db.session.commit()
        
        AuditService.log_action(
            action='UPDATE_CATEGORY',
            target_type='Category',
            target_id=category.id,
            details={'name': category.name}
        )
        flash('Category updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating category: {str(e)}', 'danger')
        
    return redirect(url_for('products.categories'))

@products_bp.route('/categories/<int:id>/delete', methods=['POST'])
@login_required
def delete_category(id):
    if not current_user.has_role('Admin'):
        flash('Access denied', 'danger')
        return redirect(url_for('products.index'))

    category = Category.query.get_or_404(id)
    
    # Check for associated products
    if category.products:
        flash('Cannot delete category because it contains products. Please empty existing products first.', 'warning')
        return redirect(url_for('products.categories'))

    try:
        db.session.delete(category)
        db.session.commit()
        
        AuditService.log_action(
            action='DELETE_CATEGORY',
            target_type='Category',
            target_id=category.id,
            details={'name': category.name}
        )
        flash('Category deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting category: {str(e)}', 'danger')
        
    return redirect(url_for('products.categories'))


@products_bp.route('/export/pdf')
@login_required
def export_pdf():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('products.index'))

    # Get filters
    search = request.args.get('search', '')
    category_id = request.args.get('category_id', type=int)

    # Build query
    query = Product.query
    if search:
        query = query.filter(or_(
            Product.name.contains(search),
            Product.sku.contains(search),
            Product.barcode.contains(search)
        ))
    if category_id:
        query = query.filter(Product.category_id == category_id)

    products = query.order_by(desc(Product.created_at)).all()

    # Context for template
    company_name = SystemSetting.get('company_name', 'Electronics Store')
    category_name = None
    if category_id:
        cat = Category.query.get(category_id)
        if cat:
            category_name = cat.name

    html = render_template(
        'products/pdf_export.html',
        products=products,
        company_name=company_name,
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
        category_filter=category_name,
        search_query=search,
        format_currency=format_currency
    )

    try:
        path_wkhtmltopdf = current_app.config.get('WKHTMLTOPDF_PATH')
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        pdf_bytes = pdfkit.from_string(html, False, configuration=config)
    except Exception as e:
        current_app.logger.exception("pdfkit failed to generate inventory PDF")
        flash(f"PDF generation failed: {str(e)}", "danger")
        return redirect(url_for('products.index'))

    pdf_io = BytesIO(pdf_bytes)
    pdf_io.seek(0)
    filename = f"inventory_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    return send_file(
        pdf_io,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


@products_bp.route('/export/excel')
@login_required
def export_excel():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('products.index'))

    # Get filters
    search = request.args.get('search', '')
    category_id = request.args.get('category_id', type=int)

    # Build query
    query = Product.query
    if search:
        query = query.filter(or_(
            Product.name.contains(search),
            Product.sku.contains(search),
            Product.barcode.contains(search)
        ))
    if category_id:
        query = query.filter(Product.category_id == category_id)

    products = query.order_by(desc(Product.created_at)).all()

    # Create Excel Workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventory"

    # Headers
    headers = ['ID', 'Name', 'Category', 'SKU', 'Barcode', 'Cost Price', 'Selling Price', 'Stock', 'Low Stock Threshold', 'Status']
    ws.append(headers)

    # Style Header
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    # Add Data
    for p in products:
        status = "Low Stock" if p.is_low_stock else "In Stock"
        row = [
            p.id,
            p.name,
            p.category.name if p.category else '-',
            p.sku,
            p.barcode,
            p.cost_price,
            p.selling_price,
            p.quantity_in_stock,
            p.low_stock_threshold,
            status
        ]
        ws.append(row)

    # Auto-width
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column].width = adjusted_width

    # Save to BytesIO
    excel_io = BytesIO()
    wb.save(excel_io)
    excel_io.seek(0)
    
    filename = f"inventory_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    return send_file(
        excel_io,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )
