# app/routes/customers.py
"""Customer CRUD routes with profile, ledger, and search functionality"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Customer, CustomerLedger, Sale, Payment, CustomerStatus, LedgerEntryType, InvoiceStatus, PaymentMethod, SaleStatus
from app.utils import format_currency
from datetime import datetime
from decimal import Decimal

customers_bp = Blueprint('customers', __name__, url_prefix='/customers')


# =============================================================================
# CUSTOMER LIST
# =============================================================================

@customers_bp.route('/')
@login_required
def index():
    """List all customers with search and pagination"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    per_page = 20
    
    query = Customer.query
    
    # Search filter
    if search:
        query = query.filter(
            db.or_(
                Customer.full_name.ilike(f'%{search}%'),
                Customer.phone.ilike(f'%{search}%'),
                Customer.email.ilike(f'%{search}%')
            )
        )
    
    # Status filter
    if status_filter:
        try:
            query = query.filter(Customer.status == CustomerStatus(status_filter))
        except:
            pass
    
    # Order by name
    query = query.order_by(Customer.full_name.asc())
    
    # Paginate
    customers = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('customers/index.html', 
                           customers=customers, 
                           search=search,
                           status_filter=status_filter)


# =============================================================================
# CREATE CUSTOMER
# =============================================================================

@customers_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new customer"""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip() or None
        email = request.form.get('email', '').strip() or None
        address = request.form.get('address', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        
        # Validation
        if not full_name:
            flash('Full name is required.', 'danger')
            return render_template('customers/form.html', customer=None)
        
        # Check for duplicate phone
        if phone:
            existing = Customer.query.filter_by(phone=phone).first()
            if existing:
                flash(f'Phone number already registered to {existing.full_name}.', 'danger')
                return render_template('customers/form.html', customer=None)
        
        try:
            customer = Customer(
                full_name=full_name,
                phone=phone,
                email=email,
                address=address,
                notes=notes,
                status=CustomerStatus.ACTIVE
            )
            db.session.add(customer)
            db.session.commit()
            
            flash(f'Customer "{full_name}" created successfully.', 'success')
            return redirect(url_for('customers.profile', customer_id=customer.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating customer: {str(e)}', 'danger')
    
    return render_template('customers/form.html', customer=None)


# =============================================================================
# EDIT CUSTOMER
# =============================================================================

@customers_bp.route('/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(customer_id):
    """Edit an existing customer"""
    customer = Customer.query.get_or_404(customer_id)
    
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip() or None
        email = request.form.get('email', '').strip() or None
        address = request.form.get('address', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        status = request.form.get('status', 'Active')
        
        # Validation
        if not full_name:
            flash('Full name is required.', 'danger')
            return render_template('customers/form.html', customer=customer)
        
        # Check for duplicate phone (excluding current customer)
        if phone:
            existing = Customer.query.filter(
                Customer.phone == phone, 
                Customer.id != customer_id
            ).first()
            if existing:
                flash(f'Phone number already registered to {existing.full_name}.', 'danger')
                return render_template('customers/form.html', customer=customer)
        
        try:
            customer.full_name = full_name
            customer.phone = phone
            customer.email = email
            customer.address = address
            customer.notes = notes
            customer.status = CustomerStatus(status)
            
            db.session.commit()
            flash(f'Customer "{full_name}" updated successfully.', 'success')
            return redirect(url_for('customers.profile', customer_id=customer.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating customer: {str(e)}', 'danger')
    
    return render_template('customers/form.html', customer=customer)


# =============================================================================
# CUSTOMER PROFILE
# =============================================================================

@customers_bp.route('/<int:customer_id>')
@login_required
def profile(customer_id):
    """Customer profile page with invoices, payments, and ledger"""
    customer = Customer.query.get_or_404(customer_id)
    
    # Get outstanding balance from ledger
    outstanding_balance = customer.get_outstanding_balance()
    
    # Get recent invoices (last 20)
    invoices = Sale.query.filter_by(customer_id=customer_id)\
        .order_by(Sale.created_at.desc()).limit(20).all()
    
    # Get unpaid/partial invoices
    unpaid_invoices = Sale.query.filter(
        Sale.customer_id == customer_id,
        Sale.invoice_status.in_([InvoiceStatus.UNPAID, InvoiceStatus.PARTIAL])
    ).order_by(Sale.created_at.desc()).all()
    
    # Get recent payments (last 20)
    payments = Payment.query.filter_by(customer_id=customer_id)\
        .order_by(Payment.created_at.desc()).limit(20).all()
    
    # Get recent ledger entries (last 30)
    ledger_entries = CustomerLedger.query.filter_by(customer_id=customer_id)\
        .order_by(CustomerLedger.created_at.desc(), CustomerLedger.id.desc()).limit(30).all()
    
    return render_template('customers/profile.html',
                           customer=customer,
                           outstanding_balance=outstanding_balance,
                           invoices=invoices,
                           unpaid_invoices=unpaid_invoices,
                           payments=payments,
                           ledger_entries=ledger_entries)


# =============================================================================
# DELETE CUSTOMER (SOFT DELETE)
# =============================================================================

@customers_bp.route('/<int:customer_id>/delete', methods=['POST'])
@login_required
def delete(customer_id):
    """Soft delete - set status to inactive"""
    customer = Customer.query.get_or_404(customer_id)
    
    # Check if customer has outstanding balance
    if customer.get_outstanding_balance() > 0:
        flash('Cannot deactivate customer with outstanding balance.', 'danger')
        return redirect(url_for('customers.profile', customer_id=customer_id))
    
    try:
        customer.status = CustomerStatus.INACTIVE
        db.session.commit()
        flash(f'Customer "{customer.full_name}" has been deactivated.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deactivating customer: {str(e)}', 'danger')
    
    return redirect(url_for('customers.index'))


# =============================================================================
# CUSTOMER SEARCH API (FOR CHECKOUT DROPDOWN)
# =============================================================================

@customers_bp.route('/api/search')
@login_required
def api_search():
    """Search customers for dropdown (returns JSON)"""
    q = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)
    
    if len(q) < 2:
        return jsonify({'customers': [], 'count': 0})
    
    customers = Customer.query.filter(
        Customer.status == CustomerStatus.ACTIVE,
        db.or_(
            Customer.full_name.ilike(f'%{q}%'),
            Customer.phone.ilike(f'%{q}%')
        )
    ).order_by(Customer.full_name.asc()).limit(limit).all()
    
    result = []
    for c in customers:
        balance = c.get_outstanding_balance()
        result.append({
            'id': c.id,
            'name': c.full_name,
            'phone': c.phone or '',
            'balance': float(balance),
            'credit_balance': float(c.get_available_credit())
        })
    
    return jsonify({'customers': result, 'count': len(result)})


# =============================================================================
# GET CUSTOMER DETAILS API
# =============================================================================

@customers_bp.route('/api/<int:customer_id>')
@login_required
def api_get(customer_id):
    """Get customer details for checkout modal"""
    customer = Customer.query.get_or_404(customer_id)
    balance = customer.get_outstanding_balance()
    
    return jsonify({
        'success': True,
        'customer': {
            'id': customer.id,
            'name': customer.full_name,
            'phone': customer.phone or '',
            'email': customer.email or '',
            'balance': balance,
            'credit_balance': float(customer.credit_balance) if customer.credit_balance else 0
        }
    })


# =============================================================================
# RECEIVE PAYMENT (PHASE 6)
# =============================================================================

@customers_bp.route('/<int:customer_id>/payment', methods=['GET', 'POST'])
@login_required
def receive_payment(customer_id):
    """Receive payment for a customer and allocate to unpaid invoices"""
    customer = Customer.query.get_or_404(customer_id)
    
    if request.method == 'POST':
        try:
            amount = Decimal(request.form.get('amount', 0))
            method_str = request.form.get('method', 'Cash')
            date_str = request.form.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
            reference = request.form.get('reference', '').strip() or None
            notes = request.form.get('notes', '').strip() or None
            
            if amount <= 0:
                flash('Payment amount must be greater than 0.', 'danger')
                return redirect(url_for('customers.receive_payment', customer_id=customer_id))
            
            # 1. Create Ledger Entry for the TOTAL amount (Single Source of Truth)
            # This immediately reduces the customer's outstanding balance
            current_balance = customer.get_outstanding_balance()
            new_balance = current_balance - amount
            
            # Re-instantiating cleanly:
            ledger_entry = CustomerLedger(
                customer_id=customer.id,
                entry_type=LedgerEntryType.PAYMENT,
                debit=Decimal('0'),
                credit=amount,
                balance_after=new_balance,
                note=f'Payment Received ({method_str})' + (f' - {notes}' if notes else ''),
                created_at=datetime.strptime(date_str, '%Y-%m-%d')
            )
            db.session.add(ledger_entry)

            # 2. Allocate to Unpaid Invoices (FIFO)
            # Get unpaid invoices sorted by date (oldest first)
            unpaid_invoices = Sale.query.filter(
                Sale.customer_id == customer_id,
                Sale.invoice_status.in_([InvoiceStatus.UNPAID, InvoiceStatus.PARTIAL])
            ).order_by(Sale.created_at.asc()).all()

            remaining_payment = amount
            allocations = []

            for invoice in unpaid_invoices:
                if remaining_payment <= 0:
                    break
                
                due = invoice.amount_due
                to_pay = min(remaining_payment, due)
                
                # Create Payment record for this invoice
                payment = Payment(
                    sale_id=invoice.id,
                    customer_id=customer.id,
                    amount=to_pay,
                    payment_method=PaymentMethod(method_str),
                    reference=reference,
                    note=notes,
                    created_by=current_user.id
                )
                db.session.add(payment)
                
                # Flush to ensure payment ID is generated and visible to relationships
                db.session.flush()
                
                # Update Invoice Status
                # Append to relationships to ensure in-memory state is up to date for immediate calculation
                # invoice.payments.append(payment) 
                
                remaining_payment -= to_pay
                allocations.append(f"{invoice.invoice_no}: {to_pay}")

            # 3. Handle Excess Payment (Credit)
            if remaining_payment > 0:
                customer.credit_balance = (customer.credit_balance or 0) + remaining_payment
                flash(f'Payment allocated. ${remaining_payment} added to credit balance.', 'info')
            
            # Commit all changes
            db.session.commit()
            
            # 4. Post-commit: Update invoice statuses
            # We need to re-fetch or iterate to call update_payment_status which uses SQL sum
            for invoice in unpaid_invoices:
                 invoice.update_payment_status()
            db.session.commit()

            flash(f'Payment of ${amount} recorded successfully.', 'success')
            return redirect(url_for('customers.profile', customer_id=customer_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error recording payment: {str(e)}', 'danger')
            return redirect(url_for('customers.receive_payment', customer_id=customer_id))

    # GET Request
    outstanding_balance = customer.get_outstanding_balance()
    unpaid_invoices = Sale.query.filter(
        Sale.customer_id == customer_id,
        Sale.invoice_status.in_([InvoiceStatus.UNPAID, InvoiceStatus.PARTIAL])
    ).order_by(Sale.created_at.asc()).all()
    
    return render_template('customers/payment.html',
                           customer=customer,
                           outstanding_balance=outstanding_balance,
                           unpaid_invoices=unpaid_invoices,
                           today=datetime.utcnow().strftime('%Y-%m-%d'))


# =============================================================================
# RECALCULATE BALANCE (FIX DATA INCONSISTENCY)
# =============================================================================

@customers_bp.route('/<int:customer_id>/recalculate', methods=['POST'])
@login_required
def recalculate_balance(customer_id):
    """Force recalculate customer balance based on Invoices vs Payments"""
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('customers.profile', customer_id=customer_id))

    customer = Customer.query.get_or_404(customer_id)
    
    try:
        # 1. Calculate Theoretical Balance
        # Total Invoices (Debit)
        total_invoices = db.session.query(db.func.sum(Sale.grand_total)).filter(
            Sale.customer_id == customer_id,
            Sale.sale_status != SaleStatus.VOIDED
        ).scalar() or Decimal('0')
        
        # Total Payments (Credit)
        total_payments = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.customer_id == customer_id
        ).scalar() or Decimal('0')
        
        theoretical_balance = total_invoices - total_payments
        
        # 2. Get Current Ledger Balance
        current_ledger_balance = customer.get_outstanding_balance()
        
        # 3. Adjust if needed
        if theoretical_balance != current_ledger_balance:
            diff = theoretical_balance - current_ledger_balance
            
            entry = CustomerLedger(
                customer_id=customer.id,
                entry_type=LedgerEntryType.ADJUSTMENT,
                balance_after=theoretical_balance,
                note='System Recalculation (Fix Data Inconsistency)',
                created_at=datetime.utcnow()
            )
            
            if diff > 0:
                # Balance needs to increase (Debit)
                entry.debit = diff
                entry.credit = 0
            else:
                # Balance needs to decrease (Credit)
                entry.debit = 0
                entry.credit = abs(diff)
                
            db.session.add(entry)
            db.session.commit()
            
            flash(f'Balance recalculated. Adjustment of {format_currency(diff)} applied.', 'success')
        else:
            flash('Balance is already correct.', 'info')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error recalculating balance: {str(e)}', 'danger')

    return redirect(url_for('customers.profile', customer_id=customer_id))
