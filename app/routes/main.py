from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.models import (Sale, Product, SaleItem, Expense, ExpenseStatus,
                        Payment, PaymentMethod, Customer, InvoiceStatus, SaleStatus)
from app import db
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import json

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    # If user is admin, they might prefer the admin dashboard, 
    # but the template dashboard.html seems to be the general one.
    
    # Get dashboard statistics
    total_sales = Sale.query.count()
    total_products = Product.query.count()
    low_stock_products = Product.query.filter(Product.quantity_in_stock <= Product.low_stock_threshold).count()
    
    # --- CASH-BASED FINANCIALS ---
    # Always sum USD-equivalent: coalesce(amount_in_usd, amount)
    # Legacy USD payments have amount_in_usd=NULL → coalesce returns amount (same value).
    # SLSH payments have amount_in_usd set to the converted USD value.
    usd_amt = func.coalesce(Payment.amount_in_usd, Payment.amount)

    # 1. Total Collected (Lifetime) - derived from Payments
    total_revenue = db.session.query(func.sum(usd_amt)).scalar() or 0

    # Get today's sales (for count)
    today = datetime.utcnow().date()
    today_sales = Sale.query.filter(func.date(Sale.created_at) == today).count()

    # 2. Today's Collected (derived from Payments made TODAY)
    today_revenue = db.session.query(func.sum(usd_amt)).filter(
        func.date(Payment.created_at) == today
    ).scalar() or 0

    # 3. Cash in Drawer (Today)
    cash_today = db.session.query(func.sum(usd_amt)).filter(
        func.date(Payment.created_at) == today,
        Payment.payment_method == PaymentMethod.CASH
    ).scalar() or 0

    # 4. Mobile Money (Today) - Zaad + E-Dahab
    mobile_today = db.session.query(func.sum(usd_amt)).filter(
        func.date(Payment.created_at) == today,
        Payment.payment_method.in_([PaymentMethod.ZAAD, PaymentMethod.E_DAHAB])
    ).scalar() or 0

    # 5. Card Payments (Today)
    card_today = db.session.query(func.sum(usd_amt)).filter(
        func.date(Payment.created_at) == today,
        Payment.payment_method == PaymentMethod.CARD
    ).scalar() or 0

    # 6. Yesterday's collected — for trend comparison
    yesterday = today - timedelta(days=1)
    yesterday_revenue = db.session.query(func.sum(usd_amt)).filter(
        func.date(Payment.created_at) == yesterday
    ).scalar() or 0

    if float(yesterday_revenue) > 0:
        today_trend_pct = round(((float(today_revenue) - float(yesterday_revenue)) / float(yesterday_revenue)) * 100, 1)
    elif float(today_revenue) > 0:
        today_trend_pct = 100.0
    else:
        today_trend_pct = 0.0

    # 7. Total customers
    total_customers = Customer.query.count()

    # 8. Unpaid customer invoices (outstanding receivables)
    unpaid_q = db.session.query(
        func.count(Sale.id),
        func.coalesce(func.sum(Sale.grand_total - Sale.amount_paid), 0)
    ).filter(
        Sale.invoice_status.in_([InvoiceStatus.UNPAID, InvoiceStatus.PARTIAL]),
        Sale.customer_id.isnot(None),
        Sale.sale_status != SaleStatus.VOIDED
    ).first()
    unpaid_count = int(unpaid_q[0] or 0)
    unpaid_value = float(unpaid_q[1] or 0)

    # 9. Pending expenses
    pending_exp_q = db.session.query(
        func.count(Expense.id),
        func.coalesce(func.sum(Expense.amount), 0)
    ).filter(Expense.status == ExpenseStatus.PENDING).first()
    pending_exp_count = int(pending_exp_q[0] or 0)
    pending_exp_amount = float(pending_exp_q[1] or 0)

    # 10. Today's collection breakdown by payment method + currency
    today_coll_rows = db.session.query(
        Payment.payment_method,
        Payment.payment_currency,
        func.sum(Payment.amount).label('original'),
        func.sum(func.coalesce(Payment.amount_in_usd, Payment.amount)).label('usd_equiv')
    ).filter(
        func.date(Payment.created_at) == today
    ).group_by(Payment.payment_method, Payment.payment_currency).all()

    today_breakdown = []
    for r in today_coll_rows:
        try:
            method = r.payment_method.value
        except Exception:
            method = str(r.payment_method or 'Unknown')
        try:
            currency = r.payment_currency.value if r.payment_currency else 'USD'
        except Exception:
            currency = 'USD'
        today_breakdown.append({
            'method': method,
            'currency': currency,
            'original': float(r.original or 0),
            'usd': float(r.usd_equiv or 0),
        })

    # Get recent sales
    recent_sales = Sale.query.order_by(desc(Sale.created_at)).limit(10).all()
    
    # Get top selling products
    top_products = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity_sold).label('total_sold')
    ).join(SaleItem).group_by(Product.id).order_by(desc('total_sold')).limit(5).all()
    
    # Get sales data for charts (last 30 days)
    sales_data = get_sales_chart_data()

    # Calculate Net Profit (REAL PROFIT based on Cash)
    # 1. Total Expenses (Paid only)
    total_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.status == ExpenseStatus.PAID).scalar() or 0
    
    # 2. Real Profit from Sales — computed entirely in SQL
    #    Logic: SUM( GREATEST(0, amount_paid - COALESCE(item_cost, 0)) )
    #    This mirrors the Python `real_profit` property: max(0, collected - cost)
    item_cost_subq = db.session.query(
        SaleItem.sale_id,
        func.coalesce(func.sum(SaleItem.quantity_sold * Product.cost_price), 0).label('total_cost')
    ).join(Product).group_by(SaleItem.sale_id).subquery()

    gross_profit = db.session.query(
        func.coalesce(func.sum(
            func.greatest(0, Sale.amount_paid - func.coalesce(item_cost_subq.c.total_cost, 0))
        ), 0)
    ).outerjoin(item_cost_subq, Sale.id == item_cost_subq.c.sale_id).scalar() or 0

    # 3. Net Profit = Real Gross Profit - Paid Expenses
    net_profit = float(gross_profit) - float(total_expenses)
    
    return render_template('dashboard.html',
                         total_sales=total_sales,
                         total_revenue=total_revenue,
                         total_products=total_products,
                         low_stock_products=low_stock_products,
                         today_sales=today_sales,
                         today_revenue=today_revenue,
                         recent_sales=recent_sales,
                         top_products=top_products,
                         sales_data=json.dumps(sales_data),
                         total_expenses=total_expenses,
                         net_profit=net_profit,
                         cash_today=cash_today,
                         mobile_today=mobile_today,
                         card_today=card_today,
                         total_customers=total_customers,
                         today_trend_pct=today_trend_pct,
                         yesterday_revenue=yesterday_revenue,
                         unpaid_count=unpaid_count,
                         unpaid_value=unpaid_value,
                         pending_exp_count=pending_exp_count,
                         pending_exp_amount=pending_exp_amount,
                         today_breakdown=json.dumps(today_breakdown))

def get_sales_chart_data():
    """Get sales data for the last 30 days - Cash Collected Basis"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    sales_data = []
    current_date = start_date
    
    while current_date <= end_date:
        # Sum PAYMENTS made on this day (USD-equivalent)
        daily_collection = db.session.query(
            func.sum(func.coalesce(Payment.amount_in_usd, Payment.amount))
        ).filter(
            func.date(Payment.created_at) == current_date.date()
        ).scalar() or 0
        
        sales_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'sales': float(daily_collection)
        })
        
        current_date += timedelta(days=1)
    
    return sales_data
