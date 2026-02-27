from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.models import Sale, Product, SaleItem, Expense, ExpenseStatus, Payment, PaymentMethod
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
    
    # 1. Total Collected (Lifetime) - derived from Payments
    total_revenue = db.session.query(func.sum(Payment.amount)).scalar() or 0
    
    # Get today's sales (for count)
    today = datetime.utcnow().date()
    today_sales = Sale.query.filter(func.date(Sale.created_at) == today).count()
    
    # 2. Today's Collected (derived from Payments made TODAY)
    today_revenue = db.session.query(func.sum(Payment.amount)).filter(
        func.date(Payment.created_at) == today
    ).scalar() or 0
    
    # 3. Cash in Drawer (Today)
    cash_today = db.session.query(func.sum(Payment.amount)).filter(
        func.date(Payment.created_at) == today,
        Payment.payment_method == PaymentMethod.CASH
    ).scalar() or 0
    
    # 4. Mobile Money (Today) - Zaad + E-Dahab
    mobile_today = db.session.query(func.sum(Payment.amount)).filter(
        func.date(Payment.created_at) == today,
        Payment.payment_method.in_([PaymentMethod.ZAAD, PaymentMethod.E_DAHAB])
    ).scalar() or 0
    
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
                         mobile_today=mobile_today)

def get_sales_chart_data():
    """Get sales data for the last 30 days - Cash Collected Basis"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    sales_data = []
    current_date = start_date
    
    while current_date <= end_date:
        # Sum PAYMENTS made on this day, not Sales created
        daily_collection = db.session.query(func.sum(Payment.amount)).filter(
            func.date(Payment.created_at) == current_date.date()
        ).scalar() or 0
        
        sales_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'sales': float(daily_collection)
        })
        
        current_date += timedelta(days=1)
    
    return sales_data
