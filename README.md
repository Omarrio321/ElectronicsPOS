# ElectroPOS — Electronics Store POS System

A professional Point of Sale and Inventory Management system built for electronics retailers. Features a full POS terminal, inventory tracking, customer CRM, sales reporting, returns/refunds, expense management, and dual-currency (USD + SLSH) support.

---

## Features

- **POS Terminal** — barcode scanning, product search, cart management, split payments
- **Dual Currency** — USD and Somali Shilling (SLSH) with live exchange rate
- **Inventory** — SKU/barcode tracking, low-stock alerts, image uploads, categories
- **Customers** — CRM, store credit, ledger, partial payment tracking
- **Sales History** — filterable list, receipt/invoice printing, barcode search, Excel/PDF export
- **Returns & Voids** — full return flow with refund, inventory restore, and audit trail
- **Expenses** — categorized expense tracking with net-profit reporting
- **Reports** — daily/weekly/monthly sales charts, cashier performance, PDF + Excel export
- **Role-based Access** — Admin, Manager, Cashier roles
- **Settings** — company info, logo, tax rate, exchange rate, receipt customization

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, Flask 2.3 |
| Database | MySQL 8+ via SQLAlchemy + PyMySQL |
| Migrations | Flask-Migrate (Alembic) |
| Frontend | Bootstrap 5.3, Vanilla JS, Chart.js |
| Auth | Flask-Login + Flask-WTF (CSRF) |
| PDF | wkhtmltopdf + pdfkit |
| Excel | openpyxl |
| Barcodes | JsBarcode (browser), python-barcode + Pillow (PDF) |

---

## Prerequisites

Install these on the new PC **before** running the project:

### 1. Python 3.10 or newer
Download from https://www.python.org/downloads/

During install: check **"Add Python to PATH"**

Verify: `python --version`

### 2. MySQL Server 8.0+
Download from https://dev.mysql.com/downloads/mysql/

Note down the root password you set during installation.

Verify: `mysql --version`

### 3. wkhtmltopdf (for PDF generation)
Download the Windows 64-bit installer from https://wkhtmltopdf.org/downloads.html

Install to the default path: `C:\Program Files\wkhtmltopdf\`

Verify: `"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe" --version`

### 4. Git
Download from https://git-scm.com/downloads

---

## Setup Instructions

### Step 1 — Clone the repository

```bash
git clone https://github.com/Omarrio321/ElectronicsPOS.git
cd ElectronicsPOS
```

---

### Step 2 — Create a virtual environment

```bash
python -m venv venv
```

Activate it:

- **Windows CMD:** `venv\Scripts\activate`
- **Windows PowerShell:** `venv\Scripts\Activate.ps1`
- **Git Bash / Linux / macOS:** `source venv/bin/activate`

You should see `(venv)` at the start of your prompt.

---

### Step 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

---

### Step 4 — Create the MySQL database

Open MySQL as root:

```bash
mysql -u root -p
```

Run these commands:

```sql
CREATE DATABASE electronics_pos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

> For running the test suite (optional):
> ```sql
> CREATE DATABASE electronics_pos_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
> ```

---

### Step 5 — Create the `.env` file

```bash
copy .env.example .env
```

Open `.env` in a text editor and fill in your values:

```env
# Required
SECRET_KEY=your-secret-key-here
ADMIN_PASSWORD=your-secure-admin-password

# Update with your MySQL username and password
DATABASE_URL=mysql+pymysql://root:YOUR_MYSQL_PASSWORD@localhost:3306/electronics_pos

FLASK_ENV=development
```

**Generate a secure SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Copy the output and use it as the `SECRET_KEY` value.

---

### Step 6 — Run database migrations

```bash
flask db upgrade
```

This creates all tables in the database.

---

### Step 7 — Create the admin user

```bash
flask create-admin
```

Follow the prompts to set a username and password.

---

### Step 8 — (Optional) Seed demo data

Populates the database with sample products, categories, and customers:

```bash
flask seed-data
```

---

### Step 9 — Start the application

```bash
python run.py
```

Open your browser and go to: **http://localhost:5000**

Log in with the admin credentials from Step 7.

---

## Useful CLI Commands

```bash
flask create-admin          # Create admin user interactively
flask init-db               # Create tables without migrations (first-time only)
flask db upgrade            # Apply all pending migrations
flask db migrate -m "msg"   # Generate a migration after model changes
flask seed-data             # Populate sample data
flask reset-password        # Reset a user's password
flask list-users            # List all users

pytest                      # Run all tests
pytest --cov=app            # Run tests with coverage
pytest tests/test_auth.py   # Run a specific test file
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Flask secret key for sessions and CSRF |
| `ADMIN_PASSWORD` | Yes | Used when creating the first admin via CLI |
| `DATABASE_URL` | Yes | MySQL connection string |
| `FLASK_ENV` | No | `development` (default) or `production` |
| `WKHTMLTOPDF_PATH` | No | Override wkhtmltopdf path if not in default location |
| `TEST_DATABASE_URL` | No | Separate database for running tests |

---

## Project Structure

```
electronics_pos/
├── app/
│   ├── __init__.py          # App factory (create_app)
│   ├── models.py            # All SQLAlchemy models
│   ├── routes/              # Blueprint route handlers
│   │   ├── pos.py           # POS terminal + checkout API
│   │   ├── sales.py         # Sales history, receipts, reports
│   │   ├── products.py      # Inventory management
│   │   ├── customers.py     # Customer CRM
│   │   ├── returns.py       # Returns & voids
│   │   ├── expenses.py      # Expense tracking
│   │   ├── admin.py         # User management, settings
│   │   └── auth.py          # Login / logout
│   ├── templates/           # Jinja2 HTML templates
│   ├── static/              # CSS, JS, images, uploads
│   └── services/            # Business logic (currency, audit)
├── migrations/              # Alembic migration files
├── tests/                   # pytest test suite
├── config.py                # Config classes (Dev/Prod/Test)
├── run.py                   # Application entry point
├── requirements.txt         # Python dependencies
└── .env.example             # Environment variable template
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'app'`**
The virtual environment is not activated or you are not in the project root. Run `venv\Scripts\activate` and make sure you're in the `ElectronicsPOS` folder.

**`Access denied for user 'root'@'localhost'`**
Wrong MySQL credentials in `DATABASE_URL`. Update the password in your `.env` file.

**`flask: command not found`**
Virtual environment is not activated. Run `venv\Scripts\activate` first.

**PDF generation fails or produces blank output**
wkhtmltopdf is not installed or is not found. Install it from https://wkhtmltopdf.org/downloads.html (default path is `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`). Alternatively, set `WKHTMLTOPDF_PATH` in your `.env` file to the correct path.

**`flask db upgrade` fails with "Table already exists"**
The database has tables from a previous setup. Either drop and recreate the database, or run `flask db stamp head` to mark the schema as current.

**Port 5000 already in use**
```bash
flask run --port 5001
```

---

## License

MIT License — Developed for professional business management.
