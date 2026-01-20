# app/sales.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_file
from flask_login import login_required, current_user
from app.models import db, Sale, SaleItem, Product, User, SystemSetting, PaymentMethod, SaleStatus, Expense, ExpenseCategory, ExpenseStatus
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from io import BytesIO
import pdfkit
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

sales_bp = Blueprint('sales', __name__, url_prefix='/sales')

# --------------------
# Utilities
# --------------------
def format_currency(value):
    """Format numeric value into currency string safely."""
    try:
        return "${:,.2f}".format(float(value))
    except (TypeError, ValueError):
        return "$0.00"

# --------------------
# Sales list
# --------------------
@sales_bp.route('/')
@login_required
def index():
    """
    List sales with optional filters:
      - start_date (YYYY-MM-DD)
      - end_date (YYYY-MM-DD)
      - user_id
      - page
    """
    page = request.args.get('page', 1, type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    user_id = request.args.get('user_id', type=int)

    query = Sale.query

    # parse dates (inclusive)
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Sale.created_at >= start_date)
        except ValueError:
            flash("Invalid start date format", "danger")

    if end_date_str:
        try:
            # use end of day for inclusive filter if you store times
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Sale.created_at < end_date)
        except ValueError:
            flash("Invalid end date format", "danger")

    if user_id:
        query = query.filter(Sale.user_id == user_id)

    sales = query.order_by(Sale.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    users = User.query.order_by(User.username).all()

    return render_template(
        'sales/index.html',
        sales=sales,
        users=users,
        start_date=(start_date.date() if start_date else None),
        end_date=((end_date - timedelta(days=1)).date() if end_date else None),
        user_id=user_id,
        format_currency=format_currency,
        PaymentMethod=PaymentMethod,
        SaleStatus=SaleStatus
    )

# --------------------
# Sale detail
# --------------------
@sales_bp.route('/<int:sale_id>')
@login_required
def detail(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    items = SaleItem.query.filter_by(sale_id=sale.id).order_by(SaleItem.id).all()
    return render_template(
        'sales/detail.html',
        sale=sale,
        items=items,
        format_currency=format_currency,
        PaymentMethod=PaymentMethod,
        SaleStatus=SaleStatus
    )

# --------------------
# Receipt (HTML view)
# --------------------
@sales_bp.route('/<int:sale_id>/receipt')
@login_required
def receipt(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    items = SaleItem.query.filter_by(sale_id=sale.id).order_by(SaleItem.id).all()

    company_name = SystemSetting.get('company_name', 'Electronics Store')
    receipt_header = SystemSetting.get('receipt_header', 'Electronics Store POS System')
    receipt_footer = SystemSetting.get('receipt_footer', 'Thank you for your business!')

    return render_template(
        'sales/receipt.html',
        sale=sale,
        items=items,
        company_name=company_name,
        receipt_header=receipt_header,
        receipt_footer=receipt_footer,
        format_currency=format_currency,
        PaymentMethod=PaymentMethod
    )

# --------------------
# Receipt PDF (download)
# --------------------
@sales_bp.route('/<int:sale_id>/receipt/pdf')
@login_required
def receipt_pdf(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    items = SaleItem.query.filter_by(sale_id=sale.id).order_by(SaleItem.id).all()

    company_name = SystemSetting.get('company_name', 'Electronics Store')
    receipt_header = SystemSetting.get('receipt_header', 'Electronics Store POS System')
    receipt_footer = SystemSetting.get('receipt_footer', 'Thank you for your business!')

    # Render PDF-friendly HTML template
    # Create a dedicated template 'sales/receipt_pdf.html' or reuse 'receipt.html' if that works well
    html = render_template(
        'sales/receipt_pdf.html',  # ensure this template exists and is printable
        sale=sale,
        items=items,
        company_name=company_name,
        receipt_header=receipt_header,
        receipt_footer=receipt_footer,
        format_currency=format_currency,
        PaymentMethod=PaymentMethod
    )

    # Generate PDF bytes
    try:
        path_wkhtmltopdf = current_app.config.get('WKHTMLTOPDF_PATH')
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        pdf_bytes = pdfkit.from_string(html, False, configuration=config)
    except Exception as e:
        current_app.logger.exception("pdfkit failed to generate PDF")
        flash("PDF generation failed: " + str(e), "danger")
        return redirect(url_for('sales.detail', sale_id=sale.id))

    pdf_io = BytesIO(pdf_bytes)
    pdf_io.seek(0)
    filename = f"receipt_{sale.id}.pdf"

    # send as attachment for download
    return send_file(
        pdf_io,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


# --------------------
# Recent Sales PDF
# --------------------
@sales_bp.route('/recent/pdf')
@login_required
def recent_pdf():
    """
    Generate PDF for the current list of sales (respecting filters).
    """
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    user_id = request.args.get('user_id', type=int)

    query = Sale.query

    # parse dates (inclusive)
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Sale.created_at >= start_date)
        except ValueError:
            flash("Invalid start date format", "danger")

    if end_date_str:
        try:
            # use end of day for inclusive filter if you store times
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Sale.created_at < end_date)
        except ValueError:
            flash("Invalid end date format", "danger")

    if user_id:
        query = query.filter(Sale.user_id == user_id)

    # Get all matching sales (no pagination for PDF)
    sales = query.order_by(Sale.created_at.desc()).limit(500).all() # Limit to avoid massive PDFs

    # Calculate totals for the PDF
    total_subtotal = sum(s.subtotal for s in sales)
    total_tax = sum(s.tax_amount for s in sales)
    total_discount = sum(s.discount for s in sales)
    total_grand = sum(s.grand_total for s in sales)

    company_name = SystemSetting.get('company_name', 'Electronics Store')
    
    # Resolve user name for title if filtered
    user_filter_name = None
    if user_id:
        u = User.query.get(user_id)
        if u:
            user_filter_name = u.username

    html = render_template(
        'sales/list_pdf.html',
        sales=sales,
        company_name=company_name,
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
        start_date=start_date_str,
        end_date=end_date_str,
        user_filter=user_filter_name,
        total_subtotal=total_subtotal,
        total_tax=total_tax,
        total_discount=total_discount,
        total_grand=total_grand,
        format_currency=format_currency,
        PaymentMethod=PaymentMethod,
        SaleStatus=SaleStatus
    )

    try:
        # Orientation Landscape for wider tables
        path_wkhtmltopdf = current_app.config.get('WKHTMLTOPDF_PATH')
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        pdf_bytes = pdfkit.from_string(html, False, options={'orientation': 'Landscape'}, configuration=config)
    except Exception as e:
        current_app.logger.exception("pdfkit failed to generate sales list PDF")
        flash("PDF generation failed: " + str(e), "danger")
        return redirect(url_for('sales.index'))

    pdf_io = BytesIO(pdf_bytes)
    pdf_io.seek(0)
    filename = f"sales_list_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    return send_file(
        pdf_io,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


# --------------------
# Sales List Excel Export
# --------------------
@sales_bp.route('/export/excel')
@login_required
def export_excel():
    """
    Generate Excel export for the current list of sales (respecting filters).
    """
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    user_id = request.args.get('user_id', type=int)

    query = Sale.query

    # parse dates (inclusive)
    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Sale.created_at >= start_date)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Sale.created_at < end_date)
        except ValueError:
            pass

    if user_id:
        query = query.filter(Sale.user_id == user_id)

    # Get all matching sales (limit to avoid massive exports)
    sales = query.order_by(Sale.created_at.desc()).limit(500).all()

    # Create Excel Workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales"

    # Headers
    headers = ['ID', 'Date', 'Cashier', 'Items', 'Subtotal', 'Tax', 'Discount', 'Total', 'Payment', 'Status']
    ws.append(headers)

    # Style Header
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    # Add Data
    for sale in sales:
        try:
            payment = sale.payment_method.value
        except Exception:
            payment = str(sale.payment_method)
        
        try:
            status = sale.sale_status.value
        except Exception:
            status = str(sale.sale_status)

        row = [
            sale.id,
            sale.created_at.strftime('%Y-%m-%d %H:%M'),
            sale.user.username if sale.user else '-',
            len(sale.sale_items),
            float(sale.subtotal or 0),
            float(sale.tax_amount or 0),
            float(sale.discount or 0),
            float(sale.grand_total or 0),
            payment,
            status
        ]
        ws.append(row)

    # Auto-width columns
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
    
    filename = f"sales_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    return send_file(
        excel_io,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

# --------------------
# Reports page (HTML)
# --------------------
@sales_bp.route('/reports')
@login_required
def reports():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('main.dashboard'))

    """
    Renders the reports page and injects arrays expected by the template:
      - daily_sales: list of {date: 'YYYY-MM-DD', sales: float} for each day in the range
      - payment_method_labels: [...], payment_method_values: [...]
      - top_products, user_sales, totals...
    """
    report_type = request.args.get('type', 'daily')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    today = datetime.utcnow().date()
    start_date = None
    end_date = None

    # default ranges
    if report_type == 'daily':
        start_date = end_date = today
    elif report_type == 'weekly':
        end_date = today
        start_date = today - timedelta(days=7)
    elif report_type == 'monthly':
        end_date = today
        start_date = today.replace(day=1)

    # override with provided dates (custom)
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid start date', 'danger')
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid end date', 'danger')

    # fallback if dates missing
    if not start_date or not end_date:
        end_date = today
        start_date = today - timedelta(days=30)

    # Build daily sales query and fill gaps
    rows = db.session.query(
        func.date(Sale.created_at).label('date'),
        func.coalesce(func.sum(Sale.grand_total), 0).label('sales')
    ).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

    row_map = {str(r.date): float(r.sales or 0) for r in rows}
    daily_sales = []
    cursor = start_date
    while cursor <= end_date:
        key = cursor.strftime('%Y-%m-%d')
        daily_sales.append({'date': key, 'sales': float(row_map.get(key, 0.0))})
        cursor += timedelta(days=1)

    # Payment methods (labels + values)
    pm_rows = db.session.query(
        Sale.payment_method,
        func.coalesce(func.sum(Sale.grand_total), 0).label('total')
    ).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(Sale.payment_method).all()

    pm_labels = []
    pm_values = []
    for r in pm_rows:
        try:
            label = r.payment_method.value  # if Enum
        except Exception:
            label = str(r.payment_method)
        pm_labels.append(label)
        pm_values.append(float(r.total or 0))

    # Totals and aggregates
    total_sales = db.session.query(func.count(Sale.id)).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0

    total_revenue = db.session.query(func.coalesce(func.sum(Sale.grand_total), 0)).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0

    total_items = db.session.query(func.coalesce(func.sum(SaleItem.quantity_sold), 0)).join(Sale, SaleItem.sale).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0

    low_stock_count = Product.query.filter(Product.quantity_in_stock <= Product.low_stock_threshold).count()

    # --- COGS (Cost of Goods Sold) ---
    # Calculate cost of products sold in the period
    cogs = db.session.query(
        func.coalesce(func.sum(SaleItem.quantity_sold * Product.cost_price), 0)
    ).join(Product).join(Sale, SaleItem.sale).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0

    # Gross Profit = Revenue - COGS
    gross_profit = float(total_revenue) - float(cogs)

    # Average Order Value
    avg_order_value = float(total_revenue) / float(total_sales) if total_sales > 0 else 0

    # Top products
    top_products = db.session.query(
        Product.name,
        func.coalesce(func.sum(SaleItem.quantity_sold), 0).label('total_sold'),
        func.coalesce(func.sum(SaleItem.total_price), 0).label('total_revenue')
    ).join(SaleItem).join(Sale).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(Product.id).order_by(func.sum(SaleItem.quantity_sold).desc()).limit(10).all()

    # Sales by cashier
    user_sales = db.session.query(
        User.username,
        func.count(Sale.id).label('count'),
        func.coalesce(func.sum(Sale.grand_total), 0).label('total')
    ).join(Sale).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(User.id).order_by(func.sum(Sale.grand_total).desc()).all()

    # --- EXPENSES INTEGRATION ---
    # Only PAID expenses count towards net profit calculation
    paid_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.date >= start_date,
        Expense.date <= end_date,
        Expense.status == ExpenseStatus.PAID
    ).scalar() or 0

    # Track pending expenses separately for visibility
    pending_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.date >= start_date,
        Expense.date <= end_date,
        Expense.status == ExpenseStatus.PENDING
    ).scalar() or 0

    # Total expenses (all statuses) for reporting purposes
    total_expenses = float(paid_expenses) + float(pending_expenses)

    # Net profit = Revenue - COGS - Paid Expenses (matches dashboard formula)
    net_profit = float(total_revenue) - float(cogs) - float(paid_expenses)

    # Expense Distribution by Category (PAID only for chart accuracy)
    exp_stats = db.session.query(
        ExpenseCategory.name,
        func.coalesce(func.sum(Expense.amount), 0).label('total'),
        ExpenseCategory.color
    ).join(Expense).filter(
        Expense.date >= start_date,
        Expense.date <= end_date,
        Expense.status == ExpenseStatus.PAID
    ).group_by(ExpenseCategory.id).all()

    exp_labels = [r[0] for r in exp_stats]
    exp_values = [float(r[1]) for r in exp_stats]
    exp_colors = [r[2] for r in exp_stats]

    # Recent Expenses for table (show all statuses for context)
    recent_expenses = Expense.query.filter(
        Expense.date >= start_date,
        Expense.date <= end_date
    ).order_by(Expense.date.desc()).limit(10).all()

    # Render template: these keys match the shape used by the templates provided earlier
    return render_template(
        'sales/reports.html',
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        total_sales=int(total_sales),
        total_revenue=float(total_revenue),
        total_items=int(total_items),
        cogs=float(cogs),
        gross_profit=gross_profit,
        avg_order_value=avg_order_value,
        paid_expenses=float(paid_expenses),
        pending_expenses=float(pending_expenses),
        total_expenses=float(total_expenses),
        net_profit=net_profit,
        low_stock_count=int(low_stock_count),
        daily_sales=daily_sales,
        payment_method_labels=pm_labels,
        payment_method_values=pm_values,
        expense_labels=exp_labels,
        expense_values=exp_values,
        expense_colors=exp_colors,
        recent_expenses=recent_expenses,
        top_products=top_products,
        user_sales=user_sales,
        format_currency=format_currency
    )

# --------------------
# Reports JSON (AJAX)
# --------------------
@sales_bp.route('/reports/data')
@login_required
def reports_data():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        return jsonify({'error': 'Access denied'}), 403

    """
    Minimal JSON endpoint used by older versions / AJAX.
    Returns:
      { daily_sales: [{date, sales}, ...], payment_methods: { labels:[], values:[] } }
    Default: last 30 days
    """
    today = datetime.utcnow().date()
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    report_type = request.args.get('type', 'daily')

    if start and end:
        try:
            start_date = datetime.strptime(start, '%Y-%m-%d').date()
            end_date = datetime.strptime(end, '%Y-%m-%d').date()
        except ValueError:
            start_date = today - timedelta(days=30)
            end_date = today
    else:
        # fallback based on type
        if report_type == 'weekly':
            start_date = today - timedelta(days=7)
            end_date = today
        elif report_type == 'monthly':
            start_date = today - timedelta(days=30)
            end_date = today
        else:
            start_date = today - timedelta(days=30)
            end_date = today

    # daily sales
    rows = db.session.query(
        func.date(Sale.created_at).label('date'),
        func.coalesce(func.sum(Sale.grand_total), 0).label('sales')
    ).filter(func.date(Sale.created_at) >= start_date).filter(func.date(Sale.created_at) <= end_date).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

    daily = [{'date': str(r.date), 'sales': float(r.sales or 0)} for r in rows]

    pm_rows = db.session.query(
        Sale.payment_method,
        func.coalesce(func.sum(Sale.grand_total), 0).label('total')
    ).filter(func.date(Sale.created_at) >= start_date).filter(func.date(Sale.created_at) <= end_date).group_by(Sale.payment_method).all()

    pm_labels = []
    pm_values = []
    for r in pm_rows:
        try:
            label = r.payment_method.value
        except Exception:
            label = str(r.payment_method)
        pm_labels.append(label)
        pm_values.append(float(r.total or 0))

    return jsonify({
        'daily_sales': daily,
        'payment_methods': {'labels': pm_labels, 'values': pm_values}
    })


# --------------------
# Reports PDF
# --------------------
@sales_bp.route('/reports/pdf')
@login_required
def reports_pdf():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('main.dashboard'))

    """
    Generate PDF for the reports page.
    """
    report_type = request.args.get('type', 'daily')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    today = datetime.utcnow().date()
    start_date = None
    end_date = None

    # default ranges
    if report_type == 'daily':
        start_date = end_date = today
    elif report_type == 'weekly':
        end_date = today
        start_date = today - timedelta(days=7)
    elif report_type == 'monthly':
        end_date = today
        start_date = today.replace(day=1)

    # override with provided dates (custom)
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # fallback
    if not start_date or not end_date:
        end_date = today
        start_date = today - timedelta(days=30)
        
    # Re-run queries for the report data
    # 1. Daily Sales
    rows = db.session.query(
        func.date(Sale.created_at).label('date'),
        func.coalesce(func.sum(Sale.grand_total), 0).label('sales')
    ).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()
    
    daily_sales = [{'date': str(r.date), 'sales': float(r.sales or 0)} for r in rows]

    # 2. Aggregates
    total_sales = db.session.query(func.count(Sale.id)).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0

    total_revenue = db.session.query(func.coalesce(func.sum(Sale.grand_total), 0)).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0

    total_items = db.session.query(func.coalesce(func.sum(SaleItem.quantity_sold), 0)).join(Sale, SaleItem.sale).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0

    # 3. Top Products
    top_products = db.session.query(
        Product.name,
        func.coalesce(func.sum(SaleItem.quantity_sold), 0).label('total_sold'),
        func.coalesce(func.sum(SaleItem.total_price), 0).label('total_revenue')
    ).join(SaleItem).join(Sale).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(Product.id).order_by(func.sum(SaleItem.quantity_sold).desc()).limit(10).all()

    # 4. Sales by cashier
    user_sales = db.session.query(
        User.username,
        func.count(Sale.id).label('count'),
        func.coalesce(func.sum(Sale.grand_total), 0).label('total')
    ).join(Sale).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(User.id).order_by(func.sum(Sale.grand_total).desc()).all()

    # 5. COGS for PDF
    cogs = db.session.query(
        func.coalesce(func.sum(SaleItem.quantity_sold * Product.cost_price), 0)
    ).join(Product).join(Sale, SaleItem.sale).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0

    gross_profit = float(total_revenue) - float(cogs)
    avg_order_value = float(total_revenue) / float(total_sales) if total_sales > 0 else 0

    # 6. Expenses for PDF - Only PAID expenses count towards net profit
    paid_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.date >= start_date,
        Expense.date <= end_date,
        Expense.status == ExpenseStatus.PAID
    ).scalar() or 0

    pending_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.date >= start_date,
        Expense.date <= end_date,
        Expense.status == ExpenseStatus.PENDING
    ).scalar() or 0

    total_expenses = float(paid_expenses) + float(pending_expenses)
    # Net profit = Revenue - COGS - Paid Expenses (matches dashboard)
    net_profit = float(total_revenue) - float(cogs) - float(paid_expenses)

    period_expenses = Expense.query.filter(
        Expense.date >= start_date,
        Expense.date <= end_date
    ).order_by(Expense.date.desc()).all()

    company_name = SystemSetting.get('company_name', 'Electronics Store')

    html = render_template(
        'sales/reports_pdf.html',
        company_name=company_name,
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
        start_date=start_date,
        end_date=end_date,
        report_type=report_type,
        total_sales=total_sales,
        total_revenue=total_revenue,
        cogs=float(cogs),
        gross_profit=gross_profit,
        avg_order_value=avg_order_value,
        paid_expenses=float(paid_expenses),
        pending_expenses=float(pending_expenses),
        total_expenses=total_expenses,
        net_profit=net_profit,
        total_items=total_items,
        daily_sales=daily_sales,
        top_products=top_products,
        user_sales=user_sales,
        period_expenses=period_expenses,
        format_currency=format_currency
    )

    try:
        path_wkhtmltopdf = current_app.config.get('WKHTMLTOPDF_PATH')
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        pdf_bytes = pdfkit.from_string(html, False, configuration=config)
    except Exception as e:
        current_app.logger.exception("pdfkit failed to generate reports PDF")
        flash("PDF generation failed: " + str(e), "danger")
        return redirect(url_for('sales.reports'))

    pdf_io = BytesIO(pdf_bytes)
    pdf_io.seek(0)
    filename = f"sales_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    return send_file(
        pdf_io,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


# --------------------
# Reports Excel Export
# --------------------
@sales_bp.route('/reports/excel')
@login_required
def reports_excel():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('main.dashboard'))

    """
    Generate Excel export for the reports page with multiple sheets.
    """
    report_type = request.args.get('type', 'daily')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    today = datetime.utcnow().date()
    start_date = None
    end_date = None

    # default ranges
    if report_type == 'daily':
        start_date = end_date = today
    elif report_type == 'weekly':
        end_date = today
        start_date = today - timedelta(days=7)
    elif report_type == 'monthly':
        end_date = today
        start_date = today.replace(day=1)

    # override with provided dates (custom)
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # fallback
    if not start_date or not end_date:
        end_date = today
        start_date = today - timedelta(days=30)

    # Gather report data
    # 1. Summary stats
    total_sales = db.session.query(func.count(Sale.id)).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0

    total_revenue = db.session.query(func.coalesce(func.sum(Sale.grand_total), 0)).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0

    total_items = db.session.query(func.coalesce(func.sum(SaleItem.quantity_sold), 0)).join(Sale, SaleItem.sale).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0

    cogs = db.session.query(
        func.coalesce(func.sum(SaleItem.quantity_sold * Product.cost_price), 0)
    ).join(Product).join(Sale, SaleItem.sale).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).scalar() or 0

    gross_profit = float(total_revenue) - float(cogs)
    avg_order_value = float(total_revenue) / float(total_sales) if total_sales > 0 else 0

    paid_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.date >= start_date,
        Expense.date <= end_date,
        Expense.status == ExpenseStatus.PAID
    ).scalar() or 0

    pending_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.date >= start_date,
        Expense.date <= end_date,
        Expense.status == ExpenseStatus.PENDING
    ).scalar() or 0

    net_profit = float(total_revenue) - float(cogs) - float(paid_expenses)

    # 2. Daily sales
    rows = db.session.query(
        func.date(Sale.created_at).label('date'),
        func.coalesce(func.sum(Sale.grand_total), 0).label('sales')
    ).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(func.date(Sale.created_at)).order_by(func.date(Sale.created_at)).all()

    daily_sales = [{'date': str(r.date), 'sales': float(r.sales or 0)} for r in rows]

    # 3. Top products
    top_products = db.session.query(
        Product.name,
        func.coalesce(func.sum(SaleItem.quantity_sold), 0).label('total_sold'),
        func.coalesce(func.sum(SaleItem.total_price), 0).label('total_revenue')
    ).join(SaleItem).join(Sale).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(Product.id).order_by(func.sum(SaleItem.quantity_sold).desc()).limit(20).all()

    # 4. Sales by cashier
    user_sales = db.session.query(
        User.username,
        func.count(Sale.id).label('count'),
        func.coalesce(func.sum(Sale.grand_total), 0).label('total')
    ).join(Sale).filter(
        func.date(Sale.created_at) >= start_date,
        func.date(Sale.created_at) <= end_date
    ).group_by(User.id).order_by(func.sum(Sale.grand_total).desc()).all()

    # Create Excel Workbook
    wb = openpyxl.Workbook()
    
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    money_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")

    # Sheet 1: Summary
    ws_summary = wb.active
    ws_summary.title = "Summary"
    
    ws_summary.append(["Sales Report Summary"])
    ws_summary['A1'].font = Font(bold=True, size=14)
    ws_summary.append([f"Period: {start_date} to {end_date}"])
    ws_summary.append([f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    ws_summary.append([])
    
    summary_data = [
        ["Metric", "Value"],
        ["Total Transactions", int(total_sales)],
        ["Total Revenue", float(total_revenue)],
        ["Total Items Sold", int(total_items)],
        ["Cost of Goods Sold (COGS)", float(cogs)],
        ["Gross Profit", float(gross_profit)],
        ["Average Order Value", float(avg_order_value)],
        ["Paid Expenses", float(paid_expenses)],
        ["Pending Expenses", float(pending_expenses)],
        ["Net Profit", float(net_profit)]
    ]
    
    for row in summary_data:
        ws_summary.append(row)
    
    for cell in ws_summary[5]:
        cell.font = header_font
        cell.fill = header_fill

    # Sheet 2: Daily Sales
    ws_daily = wb.create_sheet("Daily Sales")
    ws_daily.append(["Date", "Revenue"])
    for cell in ws_daily[1]:
        cell.font = header_font
        cell.fill = header_fill
    
    for d in daily_sales:
        ws_daily.append([d['date'], d['sales']])

    # Sheet 3: Top Products
    ws_products = wb.create_sheet("Top Products")
    ws_products.append(["Product Name", "Quantity Sold", "Revenue"])
    for cell in ws_products[1]:
        cell.font = header_font
        cell.fill = header_fill
    
    for p in top_products:
        ws_products.append([p[0], int(p[1]), float(p[2])])

    # Sheet 4: Cashier Performance
    ws_cashiers = wb.create_sheet("Cashier Performance")
    ws_cashiers.append(["Cashier", "Transactions", "Total Revenue"])
    for cell in ws_cashiers[1]:
        cell.font = header_font
        cell.fill = header_fill
    
    for u in user_sales:
        ws_cashiers.append([u[0], int(u[1]), float(u[2])])

    # Auto-width for all sheets
    for ws in wb.worksheets:
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
    
    filename = f"sales_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    return send_file(
        excel_io,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )
