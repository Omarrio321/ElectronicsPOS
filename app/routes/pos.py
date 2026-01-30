from flask import Blueprint, render_template, request, jsonify, current_app
from app.models import db, Product, Category, Sale, SaleItem, SystemSetting, Payment
from app.models import PaymentMethod, SaleStatus  # Import Enums
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from decimal import Decimal

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
    """Processes the sale transaction with split payment support."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400

        items = data.get('items', [])
        discount = Decimal(str(data.get('discount', 0)))
        payments_data = data.get('payments', [])

        if not items:
            return jsonify({'success': False, 'message': 'Cart is empty.'}), 400
        if not payments_data:
            return jsonify({'success': False, 'message': 'At least one payment method required.'}), 400

        # --- PAYMENT METHOD MAPPING ---
        PAYMENT_METHOD_MAP = {
            'Cash': PaymentMethod.CASH,
            'Card': PaymentMethod.CARD,
            'E-Dahab': PaymentMethod.E_DAHAB,
            'Zaad': PaymentMethod.ZAAD
        }

        # --- VALIDATE PAYMENTS ---
        total_paid = Decimal('0')
        digital_paid = Decimal('0')
        valid_payments = []

        for p in payments_data:
            method_str = p.get('method')
            amount = Decimal(str(p.get('amount', 0)))
            reference = p.get('reference', '')

            if amount <= 0:
                continue  # Skip zero/negative payments

            if method_str not in PAYMENT_METHOD_MAP:
                return jsonify({'success': False, 'message': f'Invalid payment method: {method_str}'}), 400

            db_method = PAYMENT_METHOD_MAP[method_str]
            total_paid += amount

            # Track digital payments (non-cash)
            if db_method != PaymentMethod.CASH:
                digital_paid += amount

            valid_payments.append({
                'method': db_method,
                'amount': amount,
                'reference': reference
            })

        if not valid_payments:
            return jsonify({'success': False, 'message': 'No valid payments provided.'}), 400

        # --- CALCULATE SUBTOTAL ---
        subtotal = Decimal('0')
        product_map = {}

        for item in items:
            product = Product.query.get(item['product_id'])
            if not product:
                return jsonify({'success': False, 'message': f'Product {item["product_id"]} not found.'}), 404
            
            if product.quantity_in_stock < item['quantity']:
                return jsonify({'success': False, 'message': f'Insufficient stock for {product.name}.'}), 400
            
            subtotal += Decimal(str(item['price'])) * item['quantity']
            product_map[product.id] = product

        # --- CALCULATE TOTALS ---
        tax_rate = Decimal(str(SystemSetting.get('tax_rate', 0.08)))
        taxable_amount = max(Decimal('0'), subtotal - discount)
        tax_amount = taxable_amount * tax_rate
        grand_total = taxable_amount + tax_amount

        # --- VALIDATION: Ensure sufficient payment ---
        if total_paid < grand_total:
            shortage = grand_total - total_paid
            return jsonify({'success': False, 'message': f'Insufficient payment. Short by ${shortage:.2f}.'}), 400

        # --- VALIDATION: Prevent digital overpayment ---
        if digital_paid > grand_total:
            overpayment = digital_paid - grand_total
            return jsonify({'success': False, 'message': f'Digital payment cannot exceed total. Overpaid by ${overpayment:.2f}. Use Cash for overpayment.'}), 400

        # --- CALCULATE CHANGE (only from cash) ---
        change_given = total_paid - grand_total

        # --- DETERMINE PRIMARY PAYMENT METHOD FOR SALE RECORD ---
        # If multiple methods, use first non-zero or fallback
        primary_method = valid_payments[0]['method'] if len(valid_payments) == 1 else PaymentMethod.CASH

        # --- CREATE SALE ---
        new_sale = Sale(
            user_id=current_user.id,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            discount=discount,
            grand_total=grand_total,
            payment_method=primary_method,
            amount_paid=total_paid,
            change_given=change_given,
            sale_status=SaleStatus.COMPLETED,
            created_at=datetime.utcnow()
        )
        
        db.session.add(new_sale)
        db.session.flush()

        # --- CREATE SALE ITEMS ---
        for item in items:
            product = product_map[item['product_id']]
            
            sale_item = SaleItem(
                sale_id=new_sale.id,
                product_id=product.id,
                quantity_sold=item['quantity'],
                unit_price_at_time=Decimal(str(item['price'])),
                total_price=item['quantity'] * Decimal(str(item['price']))
            )
            db.session.add(sale_item)
            product.quantity_in_stock -= item['quantity']

        # --- CREATE PAYMENT RECORDS ---
        for p in valid_payments:
            payment = Payment(
                sale_id=new_sale.id,
                amount=p['amount'],
                payment_method=p['method'],
                reference=p['reference'] if p['reference'] else None,
                created_at=datetime.utcnow()
            )
            db.session.add(payment)

        # --- COMMIT ---
        db.session.commit()

        # --- LOG TRANSACTION ---
        from app.services.audit_service import AuditService
        AuditService.log_action(
            action='POS_CHECKOUT',
            target_type='Sale',
            target_id=new_sale.id,
            details={
                'grand_total': float(grand_total),
                'items_count': len(items),
                'payments': [{'method': p['method'].value, 'amount': float(p['amount'])} for p in valid_payments],
                'change_given': float(change_given)
            }
        )

        return jsonify({
            'success': True,
            'sale_id': new_sale.id,
            'total': float(grand_total),
            'change': float(change_given)
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


# =============================================================================
# HOLD SALE API ENDPOINTS
# =============================================================================

from app.models import HeldSale
import json

@pos_bp.route('/api/hold', methods=['POST'])
@login_required
def hold_sale():
    """Hold the current cart for later retrieval."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400
        
        cart = data.get('cart', [])
        customer_name = data.get('customer_name', '').strip() or None
        
        if not cart:
            return jsonify({'success': False, 'message': 'Cart is empty. Nothing to hold.'}), 400
        
        # Calculate totals for display in held list
        total_amount = sum(item['price'] * item['quantity'] for item in cart)
        item_count = sum(item['quantity'] for item in cart)
        
        held_sale = HeldSale(
            user_id=current_user.id,
            customer_name=customer_name,
            cart_data=json.dumps(cart),
            total_amount=Decimal(str(total_amount)),
            item_count=item_count
        )
        
        db.session.add(held_sale)
        db.session.commit()
        
        current_app.logger.info(f"Sale held: ID={held_sale.id}, Customer={customer_name}, Items={item_count}")
        
        return jsonify({
            'success': True,
            'message': 'Sale held successfully',
            'held_id': held_sale.id
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Hold Sale Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@pos_bp.route('/api/held', methods=['GET'])
@login_required
def get_held_sales():
    """Get all held sales for the current user."""
    try:
        held_sales = HeldSale.query.filter_by(user_id=current_user.id)\
            .order_by(HeldSale.created_at.desc()).all()
        
        result = []
        for hs in held_sales:
            result.append({
                'id': hs.id,
                'customer_name': hs.customer_name or 'Customer',
                'total_amount': float(hs.total_amount),
                'item_count': hs.item_count,
                'created_at': hs.created_at.strftime('%H:%M') if hs.created_at else ''
            })
        
        return jsonify({
            'success': True,
            'held_sales': result,
            'count': len(result)
        })
        
    except Exception as e:
        current_app.logger.error(f"Get Held Sales Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@pos_bp.route('/api/held/<int:held_id>/resume', methods=['POST'])
@login_required
def resume_held_sale(held_id):
    """Resume a held sale by returning the cart data."""
    try:
        held_sale = HeldSale.query.filter_by(id=held_id, user_id=current_user.id).first()
        
        if not held_sale:
            return jsonify({'success': False, 'message': 'Held sale not found'}), 404
        
        cart_data = json.loads(held_sale.cart_data)
        customer_name = held_sale.customer_name
        
        # Delete the held sale after resuming
        db.session.delete(held_sale)
        db.session.commit()
        
        current_app.logger.info(f"Sale resumed: ID={held_id}")
        
        return jsonify({
            'success': True,
            'message': 'Sale resumed',
            'cart': cart_data,
            'customer_name': customer_name
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Resume Held Sale Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@pos_bp.route('/api/held/<int:held_id>', methods=['DELETE'])
@login_required
def delete_held_sale(held_id):
    """Delete a held sale without resuming."""
    try:
        held_sale = HeldSale.query.filter_by(id=held_id, user_id=current_user.id).first()
        
        if not held_sale:
            return jsonify({'success': False, 'message': 'Held sale not found'}), 404
        
        db.session.delete(held_sale)
        db.session.commit()
        
        current_app.logger.info(f"Held sale deleted: ID={held_id}")
        
        return jsonify({
            'success': True,
            'message': 'Held sale deleted'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete Held Sale Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500