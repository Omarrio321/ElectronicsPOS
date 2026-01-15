from flask import Blueprint, render_template, request, jsonify, current_app
from app.models import db, Product, Category, Sale, SaleItem, SystemSetting
from app.models import PaymentMethod, SaleStatus  # Import Enums
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from datetime import datetime

pos_bp = Blueprint('pos', __name__, url_prefix='/pos')

@pos_bp.route('/')
@login_required
def index():
    """Renders the main POS interface."""
    return render_template('pos/index.html')

@pos_bp.route('/api/data')
@login_required
def get_pos_data():
    """Loads categories and products for the UI."""
    try:
        categories = Category.query.all()
        products = Product.query.filter_by(is_active=True).all()
        
        tax_rate = float(SystemSetting.get('tax_rate', 0.08))

        product_data = []
        for p in products:
            product_data.append({
                'id': p.id,
                'name': p.name,
                'price': float(p.selling_price),
                'stock': p.quantity_in_stock,
                'category_id': p.category_id,
                'sku': p.sku,
                'barcode': p.barcode
            })

        category_data = [{'id': c.id, 'name': c.name} for c in categories]

        return jsonify({
            'success': True,
            'tax_rate': tax_rate,
            'categories': category_data,
            'products': product_data
        })
    except Exception as e:
        current_app.logger.error(f"POS Data Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@pos_bp.route('/api/checkout', methods=['POST'])
@login_required
def checkout():
    """Processes the sale transaction."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400

        items = data.get('items', [])
        discount = float(data.get('discount', 0))
        payment_method_str = data.get('payment_method')

        if not items:
            return jsonify({'success': False, 'message': 'Cart is empty.'}), 400
        if not payment_method_str:
            return jsonify({'success': False, 'message': 'Payment method required.'}), 400

        # --- MAP FRONTEND STRINGS TO DB ENUMS ---
        if payment_method_str == 'Cash':
            db_payment_method = PaymentMethod.CASH
        else:
            db_payment_method = PaymentMethod.MOBILE_MONEY

        subtotal = 0.0
        product_map = {}

        # 1. Validate Stock & Calculate Subtotal
        for item in items:
            product = Product.query.get(item['product_id'])
            if not product:
                return jsonify({'success': False, 'message': f'Product {item["product_id"]} not found.'}), 404
            
            if product.quantity_in_stock < item['quantity']:
                return jsonify({'success': False, 'message': f'Insufficient stock for {product.name}.'}), 400
            
            subtotal += (item['price'] * item['quantity'])
            product_map[product.id] = product

        # 2. Calculate Totals
        tax_rate = float(SystemSetting.get('tax_rate', 0.08))
        
        taxable_amount = max(0, subtotal - discount)
        tax_amount = taxable_amount * tax_rate
        grand_total = taxable_amount + tax_amount

        # 3. Create Sale
        new_sale = Sale(
            user_id=current_user.id,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            discount=discount,
            grand_total=grand_total,
            payment_method=db_payment_method,
            amount_paid=grand_total,
            change_given=0.0,
            sale_status=SaleStatus.COMPLETED,
            created_at=datetime.utcnow()
        )
        
        db.session.add(new_sale)
        db.session.flush() 

        # 4. Create Sale Items
        for item in items:
            product = product_map[item['product_id']]
            
            sale_item = SaleItem(
                sale_id=new_sale.id,
                product_id=product.id,
                quantity_sold=item['quantity'],
                unit_price_at_time=item['price'],
                total_price=item['quantity'] * item['price']
            )
            db.session.add(sale_item)
            product.quantity_in_stock -= item['quantity']

        # 5. Commit
        db.session.commit()

        # 6. Log transaction
        from app.services.audit_service import AuditService
        AuditService.log_action(
            action='POS_CHECKOUT',
            target_type='Sale',
            target_id=new_sale.id,
            details={
                'grand_total': float(grand_total),
                'items_count': len(items),
                'payment_method': payment_method_str
            }
        )

        return jsonify({
            'success': True,
            'sale_id': new_sale.id,
            'total': grand_total
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Checkout Exception: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@pos_bp.route('/receipt/<int:sale_id>')
@login_required
def receipt(sale_id):
    """Renders a professional receipt page for a specific sale."""
    # sale_id is automatically converted to int by Flask
    sale = Sale.query.get_or_404(sale_id)
    
    # FIXED: Used sale_id (int) directly, not sale_id.id
    items = SaleItem.query.filter_by(sale_id=sale_id).order_by(SaleItem.id).all()
    
    return render_template('pos/receipt.html', sale=sale, items=items)