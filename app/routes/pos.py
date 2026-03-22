from flask import Blueprint, render_template, request, jsonify, current_app, url_for
from app.models import db, Product, Category, Sale, SaleItem, SystemSetting, Payment, Customer, CustomerLedger
from app.models import PaymentMethod, PaymentCurrency, SaleStatus, SaleType, InvoiceStatus, PriceType, LedgerEntryType
from app.services.currency_service import (
    get_current_exchange_rate, to_usd, is_valid_payment_combination
)
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
    """Loads categories and configuration for the UI (lightweight)."""
    try:
        categories = Category.query.all()
        tax_rate = float(SystemSetting.get('tax_rate', 0.08))
        exchange_rate = float(get_current_exchange_rate())
        category_data = [{'id': c.id, 'name': c.name} for c in categories]

        return jsonify({
            'success': True,
            'tax_rate': tax_rate,
            'exchange_rate': exchange_rate,
            'categories': category_data
        })
    except Exception as e:
        current_app.logger.error(f"POS Data Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@pos_bp.route('/api/products')
@login_required
def get_products_api():
    """Loads products with server-side pagination and filtering."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('limit', 24, type=int) # 24 is good for grids (2,3,4,6 cols)
        category_id = request.args.get('category_id', 'all')
        search = request.args.get('q', '').strip()

        query = Product.query.filter_by(is_active=True)

        # Filter by Category
        if category_id and category_id != 'all':
            try:
                query = query.filter_by(category_id=int(category_id))
            except ValueError:
                pass

        # Filter by Search (Name, SKU, Barcode)
        if search:
            query = query.filter(db.or_(
                Product.name.ilike(f'%{search}%'),
                Product.sku.ilike(f'%{search}%'),
                Product.barcode.ilike(f'%{search}%')
            ))

        # Order by name
        query = query.order_by(Product.name.asc())

        # Paginate
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        products = pagination.items

        product_data = []
        for p in products:
            product_data.append({
                'id': p.id,
                'name': p.name,
                'price': float(p.selling_price),
                'wholesale_price': float(p.wholesale_price) if p.wholesale_price else None,
                'min_wholesale_qty': p.min_wholesale_qty,
                'allow_wholesale': p.allow_wholesale,
                'stock': p.quantity_in_stock,
                'category_id': p.category_id,
                'sku': p.sku,
                'barcode': p.barcode,
                'image_url': url_for('static', filename=f'uploads/products/{p.image_filename}') if p.image_filename else None
            })

        return jsonify({
            'success': True,
            'products': product_data,
            'has_more': pagination.has_next,
            'page': page,
            'total': pagination.total
        })

    except Exception as e:
        current_app.logger.error(f"POS Product Load Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@pos_bp.route('/api/checkout', methods=['POST'])
@login_required
def checkout():
    """Processes the sale transaction with customer, wholesale, and partial payment support."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400

        items = data.get('items', [])
        discount = Decimal(str(data.get('discount', 0)))
        payments_data = data.get('payments', [])
        
        # New fields
        customer_id = data.get('customer_id')
        sale_type_str = data.get('sale_type', 'RETAIL')
        allow_partial = data.get('allow_partial_payment', False)

        if not items:
            return jsonify({'success': False, 'message': 'Cart is empty.'}), 400
        
        # Partial payments require a customer
        if allow_partial and not customer_id:
            return jsonify({'success': False, 'message': 'Customer required for partial payment.'}), 400
        
        # Validate customer if provided
        customer = None
        if customer_id:
            customer = Customer.query.get(customer_id)
            if not customer:
                return jsonify({'success': False, 'message': 'Customer not found.'}), 404

        # --- PAYMENT METHOD MAPPING ---
        PAYMENT_METHOD_MAP = {
            'Cash': PaymentMethod.CASH,
            'Card': PaymentMethod.CARD,
            'E-Dahab': PaymentMethod.E_DAHAB,
            'Zaad': PaymentMethod.ZAAD,
            'Store Credit': PaymentMethod.STORE_CREDIT
        }

        PAYMENT_CURRENCY_MAP = {
            'USD': PaymentCurrency.USD,
            'SLSH': PaymentCurrency.SLSH,
        }

        # Snapshot the exchange rate once for this entire transaction
        exchange_rate = get_current_exchange_rate()

        # --- VALIDATE PAYMENTS ---
        # All monetary comparisons are done in USD-equivalent
        total_paid_usd = Decimal('0')    # USD-equivalent total collected
        digital_paid_usd = Decimal('0')  # USD-equivalent of non-cash payments (cannot give change)
        store_credit_used = Decimal('0')
        valid_payments = []

        for p in payments_data:
            method_str = p.get('method')
            currency_str = p.get('currency', 'USD')  # Default to USD for backward compat
            amount = Decimal(str(p.get('amount', 0)))
            reference = p.get('reference', '')

            if amount <= 0:
                continue  # Skip zero/negative payments

            if method_str not in PAYMENT_METHOD_MAP:
                return jsonify({'success': False, 'message': f'Invalid payment method: {method_str}'}), 400

            if currency_str not in PAYMENT_CURRENCY_MAP:
                return jsonify({'success': False, 'message': f'Invalid currency: {currency_str}'}), 400

            db_method = PAYMENT_METHOD_MAP[method_str]
            db_currency = PAYMENT_CURRENCY_MAP[currency_str]

            # Enforce: Card is USD-only
            if not is_valid_payment_combination(db_method, db_currency):
                return jsonify({
                    'success': False,
                    'message': f'Card payments must be in USD. SLSH is not accepted via Card.'
                }), 400

            # Convert to USD equivalent for settlement arithmetic
            amount_usd = to_usd(amount, db_currency, exchange_rate)

            total_paid_usd += amount_usd

            # Track digital payments (non-cash, non-store-credit): cannot give change for these
            if db_method != PaymentMethod.CASH and db_method != PaymentMethod.STORE_CREDIT:
                digital_paid_usd += amount_usd

            # Track store credit usage
            if db_method == PaymentMethod.STORE_CREDIT:
                store_credit_used += amount_usd  # Store credit is always USD

            valid_payments.append({
                'method': db_method,
                'currency': db_currency,
                'amount': amount,           # Original amount in payment_currency
                'amount_usd': amount_usd,   # USD-equivalent
                'exchange_rate': exchange_rate,
                'reference': reference
            })
            
        # Verify store credit availability
        if store_credit_used > 0:
            if not customer:
                return jsonify({'success': False, 'message': 'Customer required for Store Credit.'}), 400

            available_credit = customer.get_available_credit()
            if store_credit_used > available_credit:
                return jsonify({'success': False,
                                'message': f'Insufficient store credit. Available: ${available_credit:.2f}'}), 400

        # For non-partial sales, require payment
        if not allow_partial and not valid_payments:
            return jsonify({'success': False, 'message': 'No valid payments provided.'}), 400

        # --- CALCULATE SUBTOTAL ---
        subtotal = Decimal('0')
        product_map = {}
        sale_type = SaleType.RETAIL
        
        if sale_type_str == 'WHOLESALE':
            sale_type = SaleType.WHOLESALE

        for item in items:
            product = Product.query.get(item['product_id'])
            if not product:
                return jsonify({'success': False, 'message': f'Product {item["product_id"]} not found.'}), 404
            
            if product.quantity_in_stock < item['quantity']:
                return jsonify({'success': False, 'message': f'Insufficient stock for {product.name}.'}), 400
            
            # Use wholesale price if applicable; always use DB price — never trust frontend price
            if sale_type == SaleType.WHOLESALE and product.wholesale_price and product.allow_wholesale:
                min_qty = product.min_wholesale_qty or 1
                if item['quantity'] < min_qty:
                    return jsonify({
                        'success': False,
                        'message': f'{product.name} requires a minimum of {min_qty} units for wholesale pricing.'
                    }), 400
                price = product.wholesale_price
            else:
                price = product.selling_price
            
            subtotal += price * item['quantity']
            product_map[product.id] = {'product': product, 'price': price}

        # --- CALCULATE TOTALS ---
        tax_rate = Decimal(str(SystemSetting.get('tax_rate', 0.08)))
        taxable_amount = max(Decimal('0'), subtotal - discount)
        tax_amount = taxable_amount * tax_rate
        grand_total = taxable_amount + tax_amount

        # --- VALIDATION (all comparisons in USD equivalent) ---
        if not allow_partial:
            if total_paid_usd < grand_total:
                shortage = grand_total - total_paid_usd
                return jsonify({'success': False,
                                'message': f'Insufficient payment. Short by ${shortage:.2f}.'}), 400

        # --- VALIDATION: Prevent digital overpayment ---
        # Digital payments (non-cash) cannot give change; store credit also cannot.
        # All amounts already converted to USD.
        if (digital_paid_usd + store_credit_used) > grand_total:
            over = (digital_paid_usd + store_credit_used) - grand_total
            return jsonify({'success': False,
                            'message': f'Digital/Credit payment cannot exceed total. Overpaid by ${over:.2f}.'}), 400

        # --- CALCULATE AMOUNTS (in USD) ---
        amount_due = max(Decimal('0'), grand_total - total_paid_usd)
        change_given = max(Decimal('0'), total_paid_usd - grand_total)

        # Determine invoice status
        if total_paid_usd >= grand_total:
            invoice_status = InvoiceStatus.PAID
        elif total_paid_usd > 0:
            invoice_status = InvoiceStatus.PARTIAL
        else:
            invoice_status = InvoiceStatus.UNPAID

        # --- DETERMINE PRIMARY PAYMENT METHOD FOR SALE RECORD ---
        primary_method = valid_payments[0]['method'] if valid_payments else PaymentMethod.CASH

        # --- GENERATE INVOICE NUMBER ---
        invoice_no = Sale.generate_invoice_no()

        # --- CREATE SALE ---
        new_sale = Sale(
            invoice_no=invoice_no,
            customer_id=customer_id,
            user_id=current_user.id,
            sale_type=sale_type,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            discount=discount,
            grand_total=grand_total,
            payment_method=primary_method,
            amount_paid=total_paid_usd,   # Always stored in USD
            amount_due=amount_due,
            change_given=change_given,
            exchange_rate_at_sale=exchange_rate,
            sale_status=SaleStatus.COMPLETED,
            invoice_status=invoice_status,
            created_at=datetime.utcnow()
        )
        
        db.session.add(new_sale)
        db.session.flush()

        # --- CREATE SALE ITEMS ---
        for item in items:
            product_info = product_map[item['product_id']]
            product = product_info['product']
            price = product_info['price']
            
            # Determine price type
            price_type = PriceType.WHOLESALE if (sale_type == SaleType.WHOLESALE and product.wholesale_price) else PriceType.RETAIL
            
            sale_item = SaleItem(
                sale_id=new_sale.id,
                product_id=product.id,
                product_name=product.name,
                product_sku=product.sku,
                quantity_sold=item['quantity'],
                unit_price_at_time=price,
                total_price=item['quantity'] * price,
                price_type=price_type
            )
            db.session.add(sale_item)
            product.quantity_in_stock -= item['quantity']

        # --- CREATE PAYMENT RECORDS ---
        for p in valid_payments:
            payment = Payment(
                sale_id=new_sale.id,
                customer_id=customer_id,
                amount=p['amount'],           # Original amount in payment_currency
                payment_method=p['method'],
                payment_currency=p['currency'],
                exchange_rate_used=p['exchange_rate'],
                amount_in_usd=p['amount_usd'],
                reference=p['reference'] if p['reference'] else None,
                created_by=current_user.id,
                created_at=datetime.utcnow()
            )
            db.session.add(payment)

        # --- HANDLE STORE CREDIT DEDUCTION ---
        if store_credit_used > 0 and customer:
            # Reduce cached credit balance (Negative balance gets closer to zero = Credit Used)
            # Actually, credit_balance field is a positive number representing available credit (from get_available_credit)
            # Wait, looking at model: credit_balance = db.Column(...) defaulting to 0. 
            # In receive_payment: customer.credit_balance += remaining_payment.
            # So it stores positive value.
            current_credit = customer.credit_balance or Decimal('0')
            customer.credit_balance = max(Decimal('0'), current_credit - store_credit_used)

        # --- CREATE LEDGER ENTRIES (if customer) ---
        if customer:
            # Get current balance
            last_entry = CustomerLedger.query.filter_by(customer_id=customer.id)\
                .order_by(CustomerLedger.id.desc()).first()
            running_balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal('0')
            
            # Invoice entry (debit - customer owes)
            # This consumes the credit (Negative Balance + Invoice Amount -> Closer to Zero or Positive)
            new_balance = running_balance + grand_total
            invoice_ledger = CustomerLedger(
                customer_id=customer.id,
                entry_type=LedgerEntryType.INVOICE,
                ref_type='Sale',
                ref_id=new_sale.id,
                debit=grand_total,
                credit=Decimal('0'),
                balance_after=new_balance,
                note=f'Invoice {invoice_no}'
            )
            db.session.add(invoice_ledger)
            running_balance = new_balance
            
            # Payment entry (credit - reduces what customer owes)
            # CRITICAL: Do NOT create a Ledger Payment entry for Store Credit
            # Store Credit payment simply means "We don't need to add a credit entry because the invoice entry already consumed the existing credit"
            # All amounts here are in USD.
            real_payment_amount = total_paid_usd - store_credit_used
            
            if real_payment_amount > 0:
                new_balance = running_balance - real_payment_amount
                payment_ledger = CustomerLedger(
                    customer_id=customer.id,
                    entry_type=LedgerEntryType.PAYMENT,
                    ref_type='Sale',
                    ref_id=new_sale.id,
                    debit=Decimal('0'),
                    credit=real_payment_amount,
                    balance_after=new_balance,
                    note=f'Payment for {invoice_no}'
                )
                db.session.add(payment_ledger)

        # --- COMMIT ---
        db.session.commit()

        # --- LOG TRANSACTION ---
        from app.services.audit_service import AuditService
        AuditService.log_action(
            action='POS_CHECKOUT',
            target_type='Sale',
            target_id=new_sale.id,
            details={
                'invoice_no': invoice_no,
                'customer_id': customer_id,
                'sale_type': sale_type.value,
                'grand_total': float(grand_total),
                'amount_paid_usd': float(total_paid_usd),
                'amount_due': float(amount_due),
                'exchange_rate': float(exchange_rate),
                'items_count': len(items),
                'payments': [
                    {
                        'method': p['method'].value,
                        'currency': p['currency'].value,
                        'amount': float(p['amount']),
                        'amount_usd': float(p['amount_usd'])
                    }
                    for p in valid_payments
                ],
                'change_given': float(change_given)
            }
        )

        return jsonify({
            'success': True,
            'sale_id': new_sale.id,
            'invoice_no': invoice_no,
            'total': float(grand_total),
            'amount_paid': float(total_paid_usd),
            'amount_due': float(amount_due),
            'change': float(change_given),
            'exchange_rate': float(exchange_rate),
            'invoice_status': invoice_status.value
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Checkout Exception: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@pos_bp.route('/receipt/<int:sale_id>')
@login_required
def receipt(sale_id):
    """Renders the thermal receipt page for a specific sale."""
    sale = Sale.query.get_or_404(sale_id)
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