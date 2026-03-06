# app/routes/returns.py
"""Return/Refund Management and Void Sale routes"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from app.models import (
    db, Sale, SaleItem, Product, Payment, Customer, CustomerLedger,
    ReturnTransaction, ReturnItem, VoidTransaction, AuditLog, SystemSetting,
    PaymentMethod, SaleStatus, InvoiceStatus, ReturnType, ReturnStatus,
    LedgerEntryType
)
from app.utils import format_currency
from decimal import Decimal
from datetime import datetime

returns_bp = Blueprint('returns', __name__, url_prefix='/sales')

# --- Payment method mapping (reused from POS) ---
PAYMENT_METHOD_MAP = {
    'Cash': PaymentMethod.CASH,
    'Card': PaymentMethod.CARD,
    'E-Dahab': PaymentMethod.E_DAHAB,
    'Zaad': PaymentMethod.ZAAD,
    'Store Credit': PaymentMethod.STORE_CREDIT,
}


# =============================================================================
# RETURN ITEMS - GET FORM
# =============================================================================

@returns_bp.route('/<int:sale_id>/return')
@login_required
def return_form(sale_id):
    """Show the return form with items and returnable quantities."""
    sale = Sale.query.get_or_404(sale_id)

    # Cannot return a voided sale
    if sale.sale_status == SaleStatus.VOIDED:
        flash('Cannot return items from a voided sale.', 'danger')
        return redirect(url_for('sales.detail', sale_id=sale.id))

    # Cannot return a fully refunded sale
    if sale.sale_status == SaleStatus.REFUNDED:
        flash('This sale has already been fully returned/refunded.', 'warning')
        return redirect(url_for('sales.detail', sale_id=sale.id))

    # Build items with returnable quantities
    items_data = []
    for item in sale.sale_items:
        returnable = sale.get_returnable_qty(item.id)
        if returnable > 0:
            items_data.append({
                'sale_item_id': item.id,
                'product_id': item.product_id,
                'product_name': item.product_name or item.product.name,
                'product_sku': item.product_sku or item.product.sku,
                'quantity_sold': item.quantity_sold,
                'returnable_qty': returnable,
                'unit_price': float(item.unit_price_at_time),
            })

    if not items_data:
        flash('No items available to return for this sale.', 'warning')
        return redirect(url_for('sales.detail', sale_id=sale.id))

    return render_template(
        'sales/return_form.html',
        sale=sale,
        items_data=items_data,
        format_currency=format_currency,
        PaymentMethod=PaymentMethod,
        SaleStatus=SaleStatus
    )


# =============================================================================
# PROCESS RETURN - POST
# =============================================================================

@returns_bp.route('/<int:sale_id>/return', methods=['POST'])
@login_required
def process_return(sale_id):
    """Process a return/refund for a sale."""
    try:
        sale = Sale.query.get_or_404(sale_id)

        # --- VALIDATION ---
        if sale.sale_status == SaleStatus.VOIDED:
            return jsonify({'success': False, 'message': 'Cannot return items from a voided sale.'}), 400

        if sale.sale_status == SaleStatus.REFUNDED:
            return jsonify({'success': False, 'message': 'This sale has already been fully returned.'}), 400

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid request data.'}), 400

        items = data.get('items', [])
        reason = data.get('reason', '').strip()
        notes = data.get('notes', '').strip()
        return_type_str = data.get('return_type', 'RETURN_AND_REFUND')
        refund_method_str = data.get('refund_method')

        if not items:
            return jsonify({'success': False, 'message': 'No items selected for return.'}), 400

        if not reason:
            return jsonify({'success': False, 'message': 'Return reason is required.'}), 400

        # Determine return type
        if return_type_str == 'RETURN_ONLY':
            return_type = ReturnType.RETURN_ONLY
            refund_method = None
        else:
            return_type = ReturnType.RETURN_AND_REFUND
            if not refund_method_str or refund_method_str not in PAYMENT_METHOD_MAP:
                return jsonify({'success': False, 'message': 'Valid refund method is required for Return & Refund.'}), 400
            refund_method = PAYMENT_METHOD_MAP[refund_method_str]

        # Walk-in customers cannot receive store credit — no account to hold it
        if return_type == ReturnType.RETURN_ONLY and not sale.customer_id:
            return jsonify({
                'success': False,
                'message': 'Store credit (Return Only) is not available for walk-in customers. Use Return & Refund instead.'
            }), 400

        # --- VALIDATE ITEMS AND CALCULATE TOTALS ---
        return_subtotal = Decimal('0')
        valid_items = []
        total_original_sold = Decimal('0')
        total_items_in_sale = len(sale.sale_items)

        for item_data in items:
            sale_item_id = item_data.get('sale_item_id')
            qty = item_data.get('quantity', 0)

            if qty <= 0:
                continue

            sale_item = SaleItem.query.get(sale_item_id)
            if not sale_item or sale_item.sale_id != sale.id:
                return jsonify({'success': False, 'message': f'Invalid sale item: {sale_item_id}'}), 400

            # Check returnable quantity
            returnable = sale.get_returnable_qty(sale_item_id)
            if qty > returnable:
                return jsonify({
                    'success': False,
                    'message': f'Return quantity ({qty}) exceeds returnable ({returnable}) for {sale_item.product_name}.'
                }), 400

            item_total = Decimal(str(qty)) * sale_item.unit_price_at_time
            return_subtotal += item_total
            total_original_sold += sale_item.total_price

            valid_items.append({
                'sale_item': sale_item,
                'quantity': qty,
                'unit_price': sale_item.unit_price_at_time,
                'total': item_total,
            })

        if not valid_items:
            return jsonify({'success': False, 'message': 'No valid items to return.'}), 400

        # --- CALCULATE PROPORTIONAL DISCOUNT AND TAX ---
        # Calculate the proportion of the return relative to the original subtotal
        original_subtotal = sale.subtotal or Decimal('1')
        proportion = return_subtotal / original_subtotal

        discount_amount = (sale.discount or Decimal('0')) * proportion
        tax_on_return = (return_subtotal - discount_amount) * sale.tax_rate
        refund_total = return_subtotal - discount_amount + tax_on_return

        # --- GENERATE RETURN NUMBER ---
        return_no = Sale.generate_return_no()

        # --- CREATE RETURN TRANSACTION ---
        return_txn = ReturnTransaction(
            return_no=return_no,
            sale_id=sale.id,
            customer_id=sale.customer_id,
            return_type=return_type,
            status=ReturnStatus.COMPLETED,
            subtotal=return_subtotal,
            tax_amount=tax_on_return,
            discount_amount=discount_amount,
            refund_total=refund_total,
            refund_method=refund_method,
            reason=reason,
            notes=notes or None,
            processed_by=current_user.id,
            created_at=datetime.utcnow()
        )
        db.session.add(return_txn)
        db.session.flush()

        # --- CREATE RETURN ITEMS AND RESTORE INVENTORY ---
        for vi in valid_items:
            return_item = ReturnItem(
                return_id=return_txn.id,
                sale_item_id=vi['sale_item'].id,
                product_id=vi['sale_item'].product_id,
                quantity_returned=vi['quantity'],
                unit_price_at_sale=vi['unit_price'],
                total_price=vi['total']
            )
            db.session.add(return_item)

            # Restore inventory
            product = Product.query.get(vi['sale_item'].product_id)
            if product:
                product.quantity_in_stock += vi['quantity']
                product.updated_at = datetime.utcnow()

        # --- UPDATE SALE STATUS ---
        # Flush so get_returnable_qty includes the items we just added
        db.session.flush()
        all_fully_returned = True
        for si in sale.sale_items:
            remaining = sale.get_returnable_qty(si.id)
            if remaining > 0:
                all_fully_returned = False
                break

        if all_fully_returned:
            sale.sale_status = SaleStatus.REFUNDED
        else:
            sale.sale_status = SaleStatus.PARTIALLY_RETURNED

        # --- HANDLE REFUND (if Return + Refund) ---
        if return_type == ReturnType.RETURN_AND_REFUND:
            # Create a negative payment record for the refund
            refund_payment = Payment(
                sale_id=sale.id,
                customer_id=sale.customer_id,
                amount=-refund_total,  # Negative = refund
                payment_method=refund_method,
                reference=f'Refund for {return_no}',
                note=f'Return refund: {return_no}',
                created_by=current_user.id,
                created_at=datetime.utcnow()
            )
            db.session.add(refund_payment)

            # Update customer ledger if customer sale
            if sale.customer_id:
                customer = Customer.query.get(sale.customer_id)
                if customer:
                    last_entry = CustomerLedger.query.filter_by(customer_id=customer.id) \
                        .order_by(CustomerLedger.id.desc()).first()
                    running_balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal('0')

                    # Credit entry: reduces what customer owes (refund)
                    new_balance = running_balance - refund_total
                    refund_ledger = CustomerLedger(
                        customer_id=customer.id,
                        entry_type=LedgerEntryType.REFUND,
                        ref_type='Return',
                        ref_id=return_txn.id,
                        debit=Decimal('0'),
                        credit=refund_total,
                        balance_after=new_balance,
                        note=f'Refund for return {return_no}'
                    )
                    db.session.add(refund_ledger)

        elif return_type == ReturnType.RETURN_ONLY and sale.customer_id:
            # Return Only with customer: add store credit via ledger entry
            customer = Customer.query.get(sale.customer_id)
            if customer:
                last_entry = CustomerLedger.query.filter_by(customer_id=customer.id) \
                    .order_by(CustomerLedger.id.desc()).first()
                running_balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal('0')

                new_balance = running_balance - refund_total
                credit_ledger = CustomerLedger(
                    customer_id=customer.id,
                    entry_type=LedgerEntryType.CREDIT_EARNED,
                    ref_type='Return',
                    ref_id=return_txn.id,
                    debit=Decimal('0'),
                    credit=refund_total,
                    balance_after=new_balance,
                    note=f'Store credit from return {return_no}'
                )
                db.session.add(credit_ledger)

        # --- AUDIT LOG (before commit so it's in the same transaction) ---
        audit_entry = AuditLog(
            user_id=current_user.id,
            action='RETURN_PROCESSED',
            target_type='ReturnTransaction',
            target_id=str(return_txn.id),
            details={
                'return_no': return_no,
                'sale_id': sale.id,
                'invoice_no': sale.invoice_no,
                'return_type': return_type.value,
                'refund_total': float(refund_total),
                'items_returned': len(valid_items),
                'reason': reason,
                'refund_method': refund_method.value if refund_method else None,
            },
            ip_address=request.remote_addr,
        )
        db.session.add(audit_entry)

        # --- COMMIT ---
        db.session.commit()

        return jsonify({
            'success': True,
            'return_id': return_txn.id,
            'return_no': return_no,
            'refund_total': float(refund_total),
            'message': f'Return {return_no} processed successfully.'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Return Processing Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# =============================================================================
# RETURN DETAIL
# =============================================================================

@returns_bp.route('/returns/<int:return_id>')
@login_required
def return_detail(return_id):
    """View return transaction details."""
    return_txn = ReturnTransaction.query.get_or_404(return_id)
    sale = Sale.query.get_or_404(return_txn.sale_id)

    return render_template(
        'sales/return_detail.html',
        return_txn=return_txn,
        sale=sale,
        format_currency=format_currency,
        PaymentMethod=PaymentMethod,
        ReturnType=ReturnType,
        ReturnStatus=ReturnStatus,
        SaleStatus=SaleStatus
    )


# =============================================================================
# RETURN RECEIPT (PRINTABLE)
# =============================================================================

@returns_bp.route('/returns/<int:return_id>/receipt')
@login_required
def return_receipt(return_id):
    """Printable return receipt."""
    return_txn = ReturnTransaction.query.get_or_404(return_id)
    sale = Sale.query.get_or_404(return_txn.sale_id)

    receipt_header = SystemSetting.get('receipt_header', 'Electronics Store POS System')
    receipt_footer = SystemSetting.get('receipt_footer', 'Thank you for your business!')

    return render_template(
        'sales/return_receipt.html',
        return_txn=return_txn,
        sale=sale,
        receipt_header=receipt_header,
        receipt_footer=receipt_footer,
        format_currency=format_currency,
        PaymentMethod=PaymentMethod,
        ReturnType=ReturnType,
        ReturnStatus=ReturnStatus
    )


# =============================================================================
# REVERSE A RETURN (Manager/Admin only)
# =============================================================================

@returns_bp.route('/returns/<int:return_id>/reverse', methods=['POST'])
@login_required
def reverse_return(return_id):
    """Reverse a completed return (Manager/Admin only)."""
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        return jsonify({'success': False, 'message': 'Manager or Admin approval required.'}), 403

    try:
        return_txn = ReturnTransaction.query.get_or_404(return_id)

        if return_txn.status == ReturnStatus.REVERSED:
            return jsonify({'success': False, 'message': 'Return is already reversed.'}), 400

        data = request.get_json() or {}
        reason = data.get('reason', '').strip()
        if not reason:
            return jsonify({'success': False, 'message': 'Reason for reversal is required.'}), 400

        sale = Sale.query.get(return_txn.sale_id)

        # Reverse inventory: deduct stock that was restored
        for ri in return_txn.items:
            product = Product.query.get(ri.product_id)
            if product:
                if product.quantity_in_stock < ri.quantity_returned:
                    return jsonify({
                        'success': False,
                        'message': f'Insufficient stock to reverse return for {product.name}. '
                                   f'Current: {product.quantity_in_stock}, Need to deduct: {ri.quantity_returned}'
                    }), 400
                product.quantity_in_stock -= ri.quantity_returned
                product.updated_at = datetime.utcnow()

        # Mark return as reversed
        return_txn.status = ReturnStatus.REVERSED
        return_txn.approved_by = current_user.id

        # Restore sale status
        if sale:
            # Check if there are other completed returns
            other_returns = ReturnTransaction.query.filter(
                ReturnTransaction.sale_id == sale.id,
                ReturnTransaction.id != return_txn.id,
                ReturnTransaction.status == ReturnStatus.COMPLETED
            ).count()

            if other_returns > 0:
                sale.sale_status = SaleStatus.PARTIALLY_RETURNED
            else:
                sale.sale_status = SaleStatus.COMPLETED

        # If there was a refund payment, reverse it
        if return_txn.return_type == ReturnType.RETURN_AND_REFUND:
            reverse_payment = Payment(
                sale_id=return_txn.sale_id,
                customer_id=return_txn.customer_id,
                amount=return_txn.refund_total,  # Positive = reversal of refund
                payment_method=return_txn.refund_method or PaymentMethod.CASH,
                reference=f'Reversal of {return_txn.return_no}',
                note=f'Return reversal: {reason}',
                created_by=current_user.id,
                created_at=datetime.utcnow()
            )
            db.session.add(reverse_payment)

            # Reverse ledger entry if customer
            if return_txn.customer_id:
                customer = Customer.query.get(return_txn.customer_id)
                if customer:
                    last_entry = CustomerLedger.query.filter_by(customer_id=customer.id) \
                        .order_by(CustomerLedger.id.desc()).first()
                    running_balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal('0')

                    new_balance = running_balance + return_txn.refund_total
                    reversal_ledger = CustomerLedger(
                        customer_id=customer.id,
                        entry_type=LedgerEntryType.ADJUSTMENT,
                        ref_type='ReturnReversal',
                        ref_id=return_txn.id,
                        debit=return_txn.refund_total,
                        credit=Decimal('0'),
                        balance_after=new_balance,
                        note=f'Reversal of return {return_txn.return_no}: {reason}'
                    )
                    db.session.add(reversal_ledger)

        elif return_txn.return_type == ReturnType.RETURN_ONLY and return_txn.customer_id:
            # Reverse store credit via ledger
            customer = Customer.query.get(return_txn.customer_id)
            if customer:
                last_entry = CustomerLedger.query.filter_by(customer_id=customer.id) \
                    .order_by(CustomerLedger.id.desc()).first()
                running_balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal('0')

                new_balance = running_balance + return_txn.refund_total
                reversal_ledger = CustomerLedger(
                    customer_id=customer.id,
                    entry_type=LedgerEntryType.ADJUSTMENT,
                    ref_type='ReturnReversal',
                    ref_id=return_txn.id,
                    debit=return_txn.refund_total,
                    credit=Decimal('0'),
                    balance_after=new_balance,
                    note=f'Credit reversal for return {return_txn.return_no}: {reason}'
                )
                db.session.add(reversal_ledger)

        # Audit log (same transaction)
        audit_entry = AuditLog(
            user_id=current_user.id,
            action='RETURN_REVERSED',
            target_type='ReturnTransaction',
            target_id=str(return_txn.id),
            details={
                'return_no': return_txn.return_no,
                'sale_id': return_txn.sale_id,
                'reason': reason,
                'reversed_by': current_user.username,
            },
            ip_address=request.remote_addr,
        )
        db.session.add(audit_entry)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Return {return_txn.return_no} has been reversed.'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Return Reversal Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# =============================================================================
# VOID SALE
# =============================================================================

@returns_bp.route('/<int:sale_id>/void', methods=['POST'])
@login_required
def void_sale(sale_id):
    """Void a sale with full audit trail."""
    try:
        sale = Sale.query.get_or_404(sale_id)

        # --- VALIDATION ---
        if sale.sale_status == SaleStatus.VOIDED:
            return jsonify({'success': False, 'message': 'This sale is already voided.'}), 400

        data = request.get_json() or {}
        reason = data.get('reason', '').strip()
        if not reason:
            return jsonify({'success': False, 'message': 'Void reason is required.'}), 400

        # Check if sale has payments - block void if paid, must use refund flow
        total_payments = sum(p.amount for p in sale.payments if p.amount > 0)
        if total_payments > 0 and sale.invoice_status in (InvoiceStatus.PAID, InvoiceStatus.PARTIAL):
            return jsonify({
                'success': False,
                'message': 'Cannot void a sale with existing payments. Use the Return/Refund flow instead.'
            }), 400

        # Check if completed sale requires manager approval (only for unpaid completed sales)
        if sale.sale_status == SaleStatus.COMPLETED:
            require_approval = SystemSetting.get('void_completed_requires_approval', 'true')
            if require_approval == 'true':
                if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
                    return jsonify({
                        'success': False,
                        'message': 'Manager or Admin approval required to void a completed sale.'
                    }), 403

        # --- RESTORE INVENTORY ---
        for item in sale.sale_items:
            product = Product.query.get(item.product_id)
            if product:
                product.quantity_in_stock += item.quantity_sold
                product.updated_at = datetime.utcnow()

        # --- MARK SALE AS VOIDED ---
        sale.sale_status = SaleStatus.VOIDED
        sale.invoice_status = InvoiceStatus.VOID
        sale.updated_at = datetime.utcnow()

        # --- CREATE VOID TRANSACTION ---
        void_txn = VoidTransaction(
            sale_id=sale.id,
            reason=reason,
            voided_by=current_user.id,
            approved_by=current_user.id if current_user.has_role('Admin') or current_user.has_role('Manager') else None,
            created_at=datetime.utcnow()
        )
        db.session.add(void_txn)

        # --- REVERSE CUSTOMER LEDGER (if customer sale) ---
        if sale.customer_id:
            customer = Customer.query.get(sale.customer_id)
            if customer:
                last_entry = CustomerLedger.query.filter_by(customer_id=customer.id) \
                    .order_by(CustomerLedger.id.desc()).first()
                running_balance = Decimal(str(last_entry.balance_after)) if last_entry else Decimal('0')

                # Credit to reverse the invoice debit
                new_balance = running_balance - sale.grand_total
                void_ledger = CustomerLedger(
                    customer_id=customer.id,
                    entry_type=LedgerEntryType.ADJUSTMENT,
                    ref_type='Void',
                    ref_id=sale.id,
                    debit=Decimal('0'),
                    credit=sale.grand_total,
                    balance_after=new_balance,
                    note=f'Void of sale {sale.invoice_no}: {reason}'
                )
                db.session.add(void_ledger)

        # --- AUDIT LOG (before commit so it's in the same transaction) ---
        audit_entry = AuditLog(
            user_id=current_user.id,
            action='SALE_VOIDED',
            target_type='Sale',
            target_id=str(sale.id),
            details={
                'invoice_no': sale.invoice_no,
                'grand_total': float(sale.grand_total),
                'reason': reason,
                'voided_by': current_user.username,
                'items_count': len(sale.sale_items),
                'sale_id': sale.id,
            },
            ip_address=request.remote_addr,
        )
        db.session.add(audit_entry)

        # --- COMMIT ---
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Sale {sale.invoice_no} has been voided.',
            'sale_id': sale.id
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Void Sale Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
