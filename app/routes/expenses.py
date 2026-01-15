from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Expense, ExpenseCategory, ExpenseType, ExpenseStatus
from datetime import datetime, date, timedelta
from sqlalchemy import func

expenses_bp = Blueprint('expenses', __name__)

@expenses_bp.route('/')
@login_required
def index():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('main.dashboard'))

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 10

    # Filters
    category_id = request.args.get('category_id', type=int)
    status_filter = request.args.get('status')
    month_filter = request.args.get('month') # YYYY-MM
    
    query = Expense.query
    
    # Date Filtering
    today = date.today()
    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            query = query.filter(Expense.date >= start_date, Expense.date <= end_date)
            current_period = start_date.strftime('%B %Y')
        except ValueError:
            current_period = "Invalid Date"
    else:
        # Default: This Month
        start_date = date(today.year, today.month, 1)
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
        query = query.filter(Expense.date >= start_date, Expense.date <= end_date)
        current_period = "This Month"

    if category_id:
        query = query.filter(Expense.category_id == category_id)
    if status_filter and status_filter in ExpenseStatus.__members__:
        query = query.filter(Expense.status == ExpenseStatus[status_filter])

    # Summaries (Optimized with SQL Aggregation)
    total_expenses = query.with_entities(func.sum(Expense.amount)).scalar() or 0
    total_paid = query.filter(Expense.status == ExpenseStatus.PAID).with_entities(func.sum(Expense.amount)).scalar() or 0
    total_pending = query.filter(Expense.status == ExpenseStatus.PENDING).with_entities(func.sum(Expense.amount)).scalar() or 0

    # Chart Data: Expenses by Category
    category_stats = db.session.query(
        ExpenseCategory.name, 
        ExpenseCategory.color, 
        func.sum(Expense.amount)
    ).join(Expense).filter(
        Expense.date >= start_date, 
        Expense.date <= end_date
    ).group_by(ExpenseCategory.id).all()

    chart_labels = [stat[0] for stat in category_stats]
    chart_colors = [stat[1] for stat in category_stats]
    chart_values = [float(stat[2]) for stat in category_stats]

    # Pagination execution
    pagination = query.order_by(Expense.date.desc()).paginate(page=page, per_page=per_page, error_out=False)
    expenses = pagination.items
    categories = ExpenseCategory.query.order_by(ExpenseCategory.name).all()

    return render_template('expenses/index.html', 
                           expenses=expenses,
                           pagination=pagination, 
                           categories=categories,
                           total_expenses=total_expenses,
                           total_paid=total_paid,
                           total_pending=total_pending,
                           current_period=current_period,
                           ExpenseType=ExpenseType,
                           ExpenseStatus=ExpenseStatus,
                           selected_month=month_filter,
                           today=today,
                           chart_labels=chart_labels,
                           chart_colors=chart_colors,
                           chart_values=chart_values)

@expenses_bp.route('/export_pdf')
@login_required
def export_pdf():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('main.dashboard'))

    # Reuse filtering logic (TODO: Refactor into shared function)
    category_id = request.args.get('category_id', type=int)
    status_filter = request.args.get('status')
    month_filter = request.args.get('month')
    
    query = Expense.query
    today = date.today()
    
    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(year, month + 1, 1) - timedelta(days=1)
            query = query.filter(Expense.date >= start_date, Expense.date <= end_date)
            current_period = start_date.strftime('%B %Y')
        except ValueError:
            current_period = "Invalid Date"
    else:
        start_date = date(today.year, today.month, 1)
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
        query = query.filter(Expense.date >= start_date, Expense.date <= end_date)
        current_period = "This Month"

    if category_id:
        query = query.filter(Expense.category_id == category_id)
    if status_filter and status_filter in ExpenseStatus.__members__:
        query = query.filter(Expense.status == ExpenseStatus[status_filter])

    expenses = query.order_by(Expense.date.desc()).all()
    
    # Calculate totals for PDF summary
    total_expenses = sum(e.amount for e in expenses)
    total_paid = sum(e.amount for e in expenses if e.status == ExpenseStatus.PAID)
    total_pending = sum(e.amount for e in expenses if e.status == ExpenseStatus.PENDING)

    # Render PDF
    from app.utils import format_currency
    from app.models import SystemSetting
    import pdfkit
    from io import BytesIO
    from flask import send_file, current_app

    company_name = SystemSetting.get('company_name', 'Electronics Store')
    
    html = render_template(
        'expenses/pdf_report.html',
        company_name=company_name,
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
        current_period=current_period,
        start_date=start_date,
        end_date=end_date,
        expenses=expenses,
        total_expenses=total_expenses,
        total_paid=total_paid,
        total_pending=total_pending,
        format_currency=format_currency
    )

    try:
        path_wkhtmltopdf = current_app.config.get('WKHTMLTOPDF_PATH')
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        pdf_bytes = pdfkit.from_string(html, False, configuration=config)
    except Exception as e:
        current_app.logger.exception("pdfkit failed to generate PDF")
        flash(f"PDF generation failed: {str(e)}", "danger")
        return redirect(url_for('expenses.index'))

    pdf_io = BytesIO(pdf_bytes)
    pdf_io.seek(0)
    filename = f"expenses_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    return send_file(
        pdf_io,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@expenses_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        title = request.form.get('title')
        amount = request.form.get('amount')
        category_id = request.form.get('category_id')
        date_str = request.form.get('date')
        type_str = request.form.get('type')
        status_str = request.form.get('status')
        notes = request.form.get('notes')
        
        try:
            expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            new_expense = Expense(
                title=title,
                amount=float(amount),
                category_id=category_id,
                user_id=current_user.id,
                date=expense_date,
                expense_type=ExpenseType[type_str],
                status=ExpenseStatus[status_str],
                notes=notes
            )
            db.session.add(new_expense)
            db.session.commit()
            flash('Expense added successfully!', 'success')
            return redirect(url_for('expenses.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding expense: {str(e)}', 'danger')
    
    categories = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    return render_template('expenses/add.html', 
                           categories=categories,
                           ExpenseType=ExpenseType,
                           ExpenseStatus=ExpenseStatus,
                           title="Add Expense",
                           btn_text="Add Expense",
                           expense=None)

@expenses_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('main.dashboard'))

    expense = Expense.query.get_or_404(id)
    if request.method == 'POST':
        try:
            expense.title = request.form.get('title')
            expense.amount = float(request.form.get('amount'))
            expense.category_id = request.form.get('category_id')
            expense.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            expense.expense_type = ExpenseType[request.form.get('type')]
            expense.status = ExpenseStatus[request.form.get('status')]
            expense.notes = request.form.get('notes')
            
            db.session.commit()
            flash('Expense updated successfully!', 'success')
            return redirect(url_for('expenses.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating expense: {str(e)}', 'danger')

    categories = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    return render_template('expenses/add.html', 
                           categories=categories,
                           ExpenseType=ExpenseType,
                           ExpenseStatus=ExpenseStatus,
                           title="Edit Expense",
                           btn_text="Update Expense",
                           expense=expense)

@expenses_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    if not current_user.has_role('Admin'):
        flash('Access denied', 'danger')
        return redirect(url_for('expenses.index'))

    expense = Expense.query.get_or_404(id)
    try:
        db.session.delete(expense)
        db.session.commit()
        flash('Expense deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting expense.', 'danger')
    return redirect(url_for('expenses.index'))

@expenses_bp.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            try:
                cat = ExpenseCategory(name=name, color=request.form.get('color', '#6c757d'))
                db.session.add(cat)
                db.session.commit()
                flash('Category added.', 'success')
            except:
                db.session.rollback()
                flash('Error adding category (duplicate name?).', 'danger')
        return redirect(url_for('expenses.categories'))

    categories = ExpenseCategory.query.order_by(ExpenseCategory.name).all()
    return render_template('expenses/categories.html', categories=categories)

@expenses_bp.route('/categories/edit/<int:id>', methods=['POST'])
@login_required
def edit_category(id):
    if not current_user.has_role('Admin') and not current_user.has_role('Manager'):
        flash('Access denied', 'danger')
        return redirect(url_for('expenses.index'))

    category = ExpenseCategory.query.get_or_404(id)
    if request.method == 'POST':
        try:
            category.name = request.form.get('name')
            category.color = request.form.get('color', '#6c757d')
            db.session.commit()
            flash('Category updated successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating category: {str(e)}', 'danger')
    return redirect(url_for('expenses.categories'))

@expenses_bp.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
def delete_category(id):
    if not current_user.has_role('Admin'):
        flash('Access denied', 'danger')
        return redirect(url_for('expenses.categories'))

    category = ExpenseCategory.query.get_or_404(id)
    
    # 1. Protect Method: Cannot delete system categories
    if category.is_system:
        flash('Cannot delete system categories.', 'danger')
        return redirect(url_for('expenses.categories'))
        
    # 2. Protect Data: Cannot delete usage
    if category.expenses:
        flash('Cannot delete category because it has associated expenses. Please reassign them first.', 'warning')
        return redirect(url_for('expenses.categories'))

    try:
        db.session.delete(category)
        db.session.commit()
        flash('Category deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting category: {str(e)}', 'danger')
            
    return redirect(url_for('expenses.categories'))
