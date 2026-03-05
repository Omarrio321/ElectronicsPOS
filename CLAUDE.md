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
- `auth_client` - Pre-authenticated client
- `admin_user`, `manager_user`, `cashier_user` - Test users by role
- `sample_category`, `sample_product` - Test inventory data
