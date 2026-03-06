# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Electronics POS - A Flask-based Point of Sale system for electronics retailers with inventory management, customer CRM, sales tracking, returns processing, and expense management.

## Tech Stack

- **Backend**: Flask 2.3.3, SQLAlchemy ORM, Flask-Migrate
- **Database**: MySQL
- **Frontend**: Bootstrap 5.3, Vanilla JS, Chart.js for reporting
- **Auth**: Flask-Login with role-based access (Admin, Manager, Cashier)
- **PDF**: wkhtmltopdf with pdfkit
- **Testing**: pytest with pytest-flask and factory-boy

## Common Commands

```bash
# Run development server
flask run
# or
python run.py

# Database migrations
flask db migrate -m "Description"
flask db upgrade

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_auth.py -v

# CLI management
flask create-admin          # Create admin user interactively
flask init-db               # Create tables & default roles
flask seed-data             # Populate sample data
flask reset-password        # Reset user password
flask list-users            # List all users
```

## Architecture

### Application Factory Pattern
`app/__init__.py` contains `create_app(config_class)` which initializes Flask with extensions (SQLAlchemy, Migrate, LoginManager, CSRFProtect, Talisman).

### Blueprint Structure
Routes are organized by domain in `app/routes/`:
- `auth.py` - Login/logout (`/auth/`)
- `main.py` - Dashboard (`/`)
- `pos.py` - POS terminal with barcode scanning (`/pos/`)
- `products.py` - Product CRUD, image uploads (`/products/`)
- `sales.py` - Sales history, PDF receipts (`/sales/`)
- `customers.py` - Customer CRM, credit balances (`/customers/`)
- `expenses.py` - Expense tracking (`/expenses/`)
- `returns.py` - Returns & refunds (`/returns/`)
- `admin.py` - User management, settings (`/admin/`)
- `api.py` - REST endpoints for AJAX (`/api/`)

### Key Models (`app/models.py`)
- **User/Role**: RBAC with Admin, Manager, Cashier roles
- **Product/Category**: Inventory with SKU, barcode, cost/selling/wholesale prices, images
- **Sale/SaleItem**: Sales transactions with line items
- **Customer/CustomerLedger**: Customer tracking, credit balance, payment history
- **Payment**: Split/partial payment support
- **ReturnTransaction/ReturnItem**: Returns with audit trail
- **VoidTransaction**: Voided sales with reason tracking
- **Expense/ExpenseCategory**: Business expenses
- **AuditLog**: System-wide audit trail

### Access Control
Use `@role_required()` decorator from `app/decorators.py` for role-based route protection.

### Template Structure
Templates in `app/templates/` inherit from `base.html`. Context processor in `app/context_processors.py` injects global settings (company name, currency format).

## Important Patterns

1. **Financial Calculations**: Always use `Decimal` from Python's decimal module, never float. Price columns use `db.Numeric(10, 2)`.

2. **Status Fields**: Use Enums defined in `app/models.py` (PaymentMethod, SaleStatus, ReturnStatus, etc.) - never raw strings.

3. **Timestamps**: Use `datetime.utcnow()` for all timestamps.

4. **AJAX Responses**: Check `request.is_json` to return JSON for AJAX requests, HTML for regular requests.

5. **Audit Logging**: Log important actions via `AuditLog` model or `app/services/audit_service.py`.

## Returns & Void System

### Returns Blueprint (`app/routes/returns.py`)
The returns blueprint registers under `/sales` prefix (shares URL space with sales blueprint).

**Routes:**
- `GET /sales/<id>/return` - Return form with returnable quantities
- `POST /sales/<id>/return` - Process return (JSON API)
- `GET /sales/returns/<id>` - Return detail view
- `GET /sales/returns/<id>/receipt` - Printable return receipt
- `POST /sales/returns/<id>/reverse` - Reverse a return (Admin/Manager only)
- `POST /sales/<id>/void` - Void a sale (JSON API)

**Business Rules:**
- Paid sales cannot be voided — use the Return/Refund flow instead
- Voiding completed sales requires Manager/Admin (controlled by `void_completed_requires_approval` SystemSetting)
- Returns calculate proportional discount and tax on returned items
- Returns restore product inventory; reversals deduct it back
- Customer ledger is updated on returns (refund credit) and reversals (debit adjustment)

### Common Pitfalls (Avoid These)

1. **MySQL ENUM changes**: Alembic does NOT auto-detect new values added to Python Enums. Always add explicit `ALTER TABLE ... MODIFY COLUMN` statements in migrations when expanding Enum values (e.g., SaleStatus gaining PARTIALLY_RETURNED, REFUNDED, VOIDED).

2. **Template null safety**: When accessing Enum `.value` in Jinja2 templates, always guard against None: `sale.sale_status.value if sale.sale_status else 'Completed'`. Do NOT use `is defined` to test attribute existence — it only tests variable names in context.

3. **Lazy-loaded relationships in templates**: If a relationship references a table that might not exist (migration not applied), the template will 500. Pass relationship data from the route with try/except fallback instead of relying on lazy loading.

4. **Report functions must be self-contained**: Each route function (`reports`, `reports_pdf`, `reports_excel`) must compute ALL variables it uses. Do NOT reference variables from other functions — they are not shared.

5. **Permission-aware tests**: Void tests that expect success (200) must use `authenticated_admin_client`, not `authenticated_cashier_client`, because the void route requires Admin/Manager for completed sales.

6. **app/__init__.py imports**: All Flask helpers used in error handlers (`flash`, `redirect`, `jsonify`, `render_template`, `request`) must be imported at the top of the file.

## Known Issues

**SECURITY**: POS checkout accepts prices from frontend without server-side verification (`app/routes/pos.py` lines 86, 122). Backend must verify prices from database.

## Configuration

Three config classes in `config.py`:
- `DevelopmentConfig`: DEBUG=True, no secure cookies
- `ProductionConfig`: DEBUG=False, secure cookies, validates SECRET_KEY
- `TestingConfig`: TESTING=True, separate test database, CSRF disabled

Environment variables in `.env` (see `.env.example`):
- `DATABASE_URL` - MySQL connection string
- `SECRET_KEY` - Flask secret key
- `ADMIN_PASSWORD` - Initial admin password

## External Dependencies

- **wkhtmltopdf**: Required for PDF generation. Windows path: `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`
- **MySQL**: Must be running with database created before `flask db upgrade`

## Test Fixtures

`tests/conftest.py` provides fixtures:
- `app`, `client` - Flask app and test client
- `authenticated_admin_client`, `authenticated_cashier_client` - Pre-authenticated clients by role
- `admin_user`, `manager_user`, `cashier_user` - Test users by role
- `category`, `product` - Test inventory data
- `db_session` - Function-scoped DB session with automatic cleanup

`tests/test_returns.py` adds:
- `test_sale` - A completed, paid sale with 2 items for testing returns/voids
