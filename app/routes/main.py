from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from app.models import Sale, Product, SaleItem, Expense, ExpenseStatus
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
    
    # Get sales data for charts (last 30 days)
    sales_data = get_sales_chart_data()

    # Calculate Net Profit
    # 1. Total Expenses (Paid only)
    total_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.status == ExpenseStatus.PAID).scalar() or 0
    
    # 2. COGS (Cost of Goods Sold)
    # COGS = Sum(Quantity Sold * Product Cost Price)
    total_cogs = db.session.query(func.sum(SaleItem.quantity_sold * Product.cost_price)).join(Product).scalar() or 0

    # 3. Net Profit
    net_profit = float(total_revenue) - float(total_cogs) - float(total_expenses)
    
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
                         net_profit=net_profit)

def get_sales_chart_data():
    """Get sales data for the last 30 days"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    sales_data = []
    current_date = start_date
    
    while current_date <= end_date:
        daily_sales = db.session.query(func.sum(Sale.grand_total)).filter(
            func.date(Sale.created_at) == current_date.date()
        ).scalar() or 0
        
        sales_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'sales': float(daily_sales)
        })
        
        current_date += timedelta(days=1)
    
    return sales_data
