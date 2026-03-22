from flask import Blueprint, jsonify, request, url_for
from flask_login import login_required, current_user
from app.models import (Product, Category, Sale, Expense, ExpenseStatus,
                        InvoiceStatus, SaleStatus, Payment, ReturnTransaction,
                        ReturnStatus, AuditLog)
from app import db
from app.decorators import role_required
from sqlalchemy import func
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/categories')
@login_required
def get_categories():
    categories = Category.query.all()
    return jsonify([{'id': c.id, 'name': c.name} for c in categories])


@api_bp.route('/notifications')
@login_required
def get_notifications():
    """Return actionable system notifications for the current user."""
    items = []
    is_manager = current_user.has_role('Admin') or current_user.has_role('Manager')
    since_24h = datetime.utcnow() - timedelta(hours=24)

    # ── 1. Out of stock (all roles) ──────────────────────────
    out_of_stock = Product.query.filter(
        Product.is_active == True,
        Product.quantity_in_stock <= 0
    ).count()
    if out_of_stock:
        sample = Product.query.filter(
            Product.is_active == True,
            Product.quantity_in_stock <= 0
        ).order_by(Product.name).limit(3).all()
        names = ', '.join(p.name for p in sample)
        if out_of_stock > 3:
            names += f' +{out_of_stock - 3} more'
        items.append({
            'id': 'out_of_stock',
            'severity': 'danger',
            'icon': 'fas fa-times-circle',
            'title': f'{out_of_stock} product{"s" if out_of_stock > 1 else ""} out of stock',
            'body': names,
            'link': '/products/low-stock',
            'time': 'Now'
        })

    # ── 2. Running low (all roles) ───────────────────────────
    running_low = Product.query.filter(
        Product.is_active == True,
        Product.quantity_in_stock > 0,
        Product.quantity_in_stock <= Product.low_stock_threshold
    ).count()
    if running_low:
        sample = Product.query.filter(
            Product.is_active == True,
            Product.quantity_in_stock > 0,
            Product.quantity_in_stock <= Product.low_stock_threshold
        ).order_by(Product.quantity_in_stock).limit(3).all()
        names = ', '.join(p.name for p in sample)
        if running_low > 3:
            names += f' +{running_low - 3} more'
        items.append({
            'id': 'low_stock',
            'severity': 'warning',
            'icon': 'fas fa-exclamation-triangle',
            'title': f'{running_low} product{"s" if running_low > 1 else ""} running low',
            'body': names,
            'link': '/products/low-stock',
            'time': 'Now'
        })

    if is_manager:
        # ── 3. Unpaid customer invoices ──────────────────────
        unpaid_count = db.session.query(func.count(Sale.id)).filter(
            Sale.invoice_status.in_([InvoiceStatus.UNPAID, InvoiceStatus.PARTIAL]),
            Sale.customer_id.isnot(None),
            Sale.sale_status != SaleStatus.VOIDED
        ).scalar() or 0
        if unpaid_count:
            unpaid_val = db.session.query(
                func.coalesce(func.sum(Sale.grand_total - Sale.amount_paid), 0)
            ).filter(
                Sale.invoice_status.in_([InvoiceStatus.UNPAID, InvoiceStatus.PARTIAL]),
                Sale.customer_id.isnot(None),
                Sale.sale_status != SaleStatus.VOIDED
            ).scalar() or 0
            items.append({
                'id': 'unpaid_invoices',
                'severity': 'warning',
                'icon': 'fas fa-file-invoice-dollar',
                'title': f'{unpaid_count} unpaid customer invoice{"s" if unpaid_count > 1 else ""}',
                'body': f'Outstanding: ${float(unpaid_val):,.2f}',
                'link': '/customers/',
                'time': 'Outstanding'
            })

        # ── 4. Pending expenses ──────────────────────────────
        pending_exp = Expense.query.filter(Expense.status == ExpenseStatus.PENDING).count()
        if pending_exp:
            pending_amt = db.session.query(func.sum(Expense.amount)).filter(
                Expense.status == ExpenseStatus.PENDING
            ).scalar() or 0
            items.append({
                'id': 'pending_expenses',
                'severity': 'info',
                'icon': 'fas fa-receipt',
                'title': f'{pending_exp} pending expense{"s" if pending_exp > 1 else ""}',
                'body': f'Awaiting payment: ${float(pending_amt):,.2f}',
                'link': '/expenses/',
                'time': 'Pending'
            })

        # ── 5. Voids in last 24h ─────────────────────────────
        void_count = db.session.query(func.count(Sale.id)).filter(
            Sale.sale_status == SaleStatus.VOIDED,
            Sale.created_at >= since_24h
        ).scalar() or 0
        if void_count:
            items.append({
                'id': 'recent_voids',
                'severity': 'info',
                'icon': 'fas fa-ban',
                'title': f'{void_count} voided sale{"s" if void_count > 1 else ""} (24h)',
                'body': 'Voided transactions require review',
                'link': '/sales/',
                'time': 'Last 24h'
            })

        # ── 6. Returns in last 24h ───────────────────────────
        ret_count = db.session.query(func.count(ReturnTransaction.id)).filter(
            ReturnTransaction.status == ReturnStatus.COMPLETED,
            ReturnTransaction.created_at >= since_24h
        ).scalar() or 0
        if ret_count:
            items.append({
                'id': 'recent_returns',
                'severity': 'info',
                'icon': 'fas fa-undo',
                'title': f'{ret_count} return{"s" if ret_count > 1 else ""} processed (24h)',
                'body': 'Return transactions completed',
                'link': '/sales/',
                'time': 'Last 24h'
            })

    return jsonify({'notifications': items, 'count': len(items)})


@api_bp.route('/scan-barcode', methods=['POST'])
@login_required
def scan_barcode():
    """Look up a product by barcode value scanned from a camera.

    Request JSON: {"barcode": "<value>"}
    Returns product data on match, or {"status": "not_found"}.
    """
    data = request.get_json(force=True, silent=True) or {}
    barcode = (data.get('barcode') or '').strip()

    if not barcode:
        return jsonify({'status': 'error', 'message': 'No barcode provided'}), 400

    product = Product.query.filter(
        Product.barcode == barcode,
        Product.is_active == True
    ).first()

    if not product:
        return jsonify({'status': 'not_found'})

    image_url = None
    if product.image_filename:
        image_url = url_for('static', filename=f'uploads/products/{product.image_filename}')

    return jsonify({
        'status': 'success',
        'product': {
            'id': product.id,
            'name': product.name,
            'price': float(product.selling_price),
            'barcode': product.barcode,
            'sku': product.sku or '',
            'stock': product.quantity_in_stock,
            'cost_price': float(product.cost_price or 0),
            'wholesale_price': float(product.wholesale_price) if product.wholesale_price else None,
            'allow_wholesale': bool(product.allow_wholesale),
            'min_wholesale_qty': product.min_wholesale_qty or 1,
            'image_url': image_url
        }
    })


@api_bp.route('/restock', methods=['POST'])
@login_required
@role_required('Admin', 'Manager')
def restock():
    """Increase a product's stock by scanning its barcode.

    Request JSON: {"barcode": "<value>", "quantity": <int>}
    Restricted to Admin and Manager roles.
    """
    data     = request.get_json(force=True, silent=True) or {}
    barcode  = (data.get('barcode') or '').strip()
    try:
        quantity = int(data.get('quantity') or 0)
    except (TypeError, ValueError):
        quantity = 0

    if not barcode:
        return jsonify({'status': 'error', 'message': 'barcode is required'}), 400
    if quantity <= 0:
        return jsonify({'status': 'error', 'message': 'quantity must be greater than 0'}), 400

    product = Product.query.filter(
        Product.barcode == barcode,
        Product.is_active == True
    ).first()

    if not product:
        return jsonify({'status': 'not_found'})

    try:
        product.update_stock(quantity)
        log = AuditLog(
            user_id=current_user.id,
            action='RESTOCK_STOCK',
            target_type='Product',
            target_id=str(product.id),
            details={
                'product': product.name,
                'barcode': barcode,
                'qty_added': quantity,
                'new_stock': product.quantity_in_stock
            },
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({
            'status': 'success',
            'product_name': product.name,
            'new_stock': product.quantity_in_stock
        })
    except ValueError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400
