# ElectroPOS — Electronics Store Point of Sale System

> A professional, production-ready Point of Sale and Inventory Management platform built for electronics retailers.

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/flask-2.3-lightgrey)
![Server](https://img.shields.io/badge/server-waitress-orange)
![License](https://img.shields.io/badge/license-proprietary-red)

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Accessing the Application](#accessing-the-application)
- [Admin Guide](#admin-guide)
- [Server Management](#server-management)
- [Project Structure](#project-structure)
- [Useful CLI Commands](#useful-cli-commands)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

ElectroPOS is a full-featured Point of Sale system designed specifically for electronics retailers. It provides a complete front-of-house POS terminal alongside back-office tools for inventory, customer relationship management, returns processing, and financial reporting — all within a single, self-hosted web application.

The system runs as a local web server accessible via the custom domain `http://Originalelectronics.local`, making it available to any device on the local network without requiring internet connectivity or cloud subscriptions. It is built on Python/Flask and served by **Waitress**, a production-grade WSGI server suitable for Windows environments.

ElectroPOS supports dual-currency operation (USD + Somaliland Shilling), role-based staff access controls, and PDF/Excel report generation — making it a complete solution for day-to-day retail operations.

---

## Features

### Point of Sale
- Full POS terminal with real-time product search and barcode scanning
- Cart management with quantity adjustment and line-item discounts
- Split-payment support (Cash, Card, Mobile Money) in USD or SLSH
- Live exchange rate conversion at checkout
- Thermal receipt printing and PDF invoice generation

### Inventory Management
- Product catalogue with SKU, barcode, cost price, selling price, and wholesale price
- Auto-generated internal barcodes with configurable prefix and padding
- Barcode label printing (standard, compact, and large formats; ZPL for thermal printers)
- Low-stock alerts and reorder threshold tracking
- Product image uploads per item
- Category-based organisation

### Customer CRM
- Full customer profiles with contact details and purchase history
- Store credit / ledger system with payment tracking
- Partial and deferred payment (invoice) support
- Debtors watchlist with outstanding balance reporting
- Customer-facing receipt and statement PDFs

### Sales & Reporting
- Complete sales history with filtering by date, cashier, and status
- PDF and Excel export for all sales lists and reports
- Daily / weekly / monthly revenue charts (Chart.js)
- Cashier performance analytics
- COGS, gross profit, net revenue, and expense summary dashboard
- Returns and voids tracked separately with full audit trail

### Returns & Voids
- Item-level partial or full return flow
- Inventory automatically restored on return; deducted again on reversal
- Customer ledger updated on refund and reversal
- Void flow for unpaid/pending sales (Manager/Admin approval configurable)

### Expense Tracking
- Categorised expense entry with receipt notes
- Monthly expense summary and PDF export
- Net profit calculation combining sales revenue and expenses

### Administration
- Role-based access: Admin, Manager, Cashier
- User management (create, edit, activate/deactivate)
- System settings: company info, logo, tax rate, exchange rate, receipt customisation
- Full audit log of every settings change and sensitive action
- **Server shutdown button** (Admin-only, in Settings → Server Control)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask 2.3 |
| Production Server | Waitress 3.x (Windows WSGI) |
| Database | MySQL 8+ via SQLAlchemy 2 + PyMySQL |
| Migrations | Flask-Migrate (Alembic) |
| Frontend | Bootstrap 5.3, Vanilla JS, Chart.js |
| Auth & Security | Flask-Login, Flask-WTF (CSRF), Flask-Talisman (CSP), Flask-Limiter |
| PDF Generation | wkhtmltopdf + pdfkit |
| Excel Export | openpyxl |
| Barcodes | python-barcode + Pillow (server); JsBarcode (browser) |
| Domain | `http://Originalelectronics.local` |

---

## System Requirements

| Requirement | Minimum |
|---|---|
| Operating System | Windows 10 / 11 (64-bit) |
| Python | 3.10 or newer |
| RAM | 2 GB (4 GB recommended) |
| MySQL | 8.0 or newer |
| wkhtmltopdf | Latest Windows build (for PDF export) |
| Browser | Chrome, Edge, or Firefox (latest) |
| Network | Local LAN for multi-device access |

> ⚠️ **Port 80** requires Administrator privileges on Windows. Run `start_server.bat` (or the desktop shortcut) as Administrator, or change the port in `.env` and update the hosts file accordingly.

---

## Installation

### Step 1 — Install prerequisites

Install the following on the machine that will run the server:

1. **Python 3.10+** — [python.org/downloads](https://www.python.org/downloads/)
   During install: check **"Add Python to PATH"**. Verify: `python --version`

2. **MySQL 8.0+** — [dev.mysql.com/downloads/mysql](https://dev.mysql.com/downloads/mysql/)
   Note down the root password set during installation. Verify: `mysql --version`

3. **wkhtmltopdf** — [wkhtmltopdf.org/downloads.html](https://wkhtmltopdf.org/downloads.html)
   Install to the default path `C:\Program Files\wkhtmltopdf\`. Required for PDF generation.

4. **Git** (optional) — [git-scm.com/downloads](https://git-scm.com/downloads)

---

### Step 2 — Get the project files

```bash
git clone https://github.com/Omarrio321/ElectronicsPOS.git
cd ElectronicsPOS
```

Or download and extract the ZIP archive to a permanent location (e.g. `D:\Projects\electronics_pos`).

---

### Step 3 — Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate
```

The prompt should show `(venv)` when the environment is active.

---

### Step 4 — Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs Flask, Waitress, SQLAlchemy, and all other dependencies.

---

### Step 5 — Create the MySQL database

```bash
mysql -u root -p
```

```sql
CREATE DATABASE electronics_pos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

> ℹ️ For the test suite (optional):
> ```sql
> CREATE DATABASE electronics_pos_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
> ```

---

### Step 6 — Configure environment variables

```bash
copy .env.example .env
```

Edit `.env` with a text editor and set your values:

```env
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
ADMIN_PASSWORD=<your-secure-admin-password>
DATABASE_URL=mysql+pymysql://root:<YOUR_MYSQL_PASSWORD>@localhost:3306/electronics_pos
FLASK_ENV=production
```

---

### Step 7 — Run database migrations

```bash
flask db upgrade
```

---

### Step 8 — Create the admin account

```bash
flask create-admin
```

Follow the prompts to set a username and password.

---

### Step 9 — Configure the custom domain (run once, as Administrator)

Right-click `setup_hosts.bat` and choose **Run as administrator**. This appends
`127.0.0.1    Originalelectronics.local` to the Windows hosts file so that the
domain resolves locally without a DNS server.

---

### Step 10 — Create the Desktop shortcut (optional but recommended)

```bash
create_shortcut.bat
```

A shortcut named **"Original Electronics"** will appear on the Desktop.

---

### Step 11 — (Optional) Seed demo data

```bash
flask seed-data
```

Populates the database with sample products, categories, and customers.

---

## Configuration

### Environment variables (`.env`)

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Flask session and CSRF secret key (min 32 random hex chars) |
| `ADMIN_PASSWORD` | Yes | Password used when creating the first admin via CLI |
| `DATABASE_URL` | Yes | MySQL connection string |
| `FLASK_ENV` | No | `production` (default for server.py) or `development` |
| `PORT` | No | Override port (default `80`). Set to `8080` to avoid admin-rights requirement |
| `WKHTMLTOPDF_PATH` | No | Full path to wkhtmltopdf binary if not in the default location |
| `TEST_DATABASE_URL` | No | Separate database URL for the test suite |

### Changing the port

If running on port 80 is not practical (e.g. another service already uses it), set `PORT=8080` in `.env` and update `setup_hosts.bat` to include the port or use the IP directly.

### Config classes (`config.py`)

| Class | Use case |
|---|---|
| `ProductionConfig` | Used by `server.py` (Waitress). `DEBUG=False`, secure cookies |
| `DevelopmentConfig` | Used by `run.py` (`flask run`). `DEBUG=True`, relaxed cookies |
| `TestingConfig` | Used by pytest. Separate DB, CSRF disabled |

---

## Running the Application

### Method 1 — Desktop shortcut (recommended for daily use)

Double-click the **"Original Electronics"** shortcut on the Desktop.
The browser opens automatically at `http://Originalelectronics.local`.
No terminal window appears.

### Method 2 — VBScript wrapper

Double-click `launcher.vbs` from the project folder. Equivalent to the
desktop shortcut — starts the server silently and opens the browser.

### Method 3 — Batch file (if terminal visibility is acceptable)

```bat
start_server.bat
```

### Method 4 — Direct Python (for debugging / development)

```bash
# Production server (Waitress, port 80)
python server.py

# Development server (Flask built-in, port 5000, auto-reload)
python run.py
```

> ℹ️ `server.py` defaults to `FLASK_ENV=production`. Pass `FLASK_ENV=development` as an environment variable to enable debug mode with Waitress (not recommended for production use).

---

## Accessing the Application

| URL | Description |
|---|---|
| `http://Originalelectronics.local` | Main application (after hosts file setup) |
| `http://localhost` | Alternative when `setup_hosts.bat` has not been run |
| `http://<LAN-IP-ADDRESS>` | Access from other devices on the same network |

**Default admin credentials** are set during `flask create-admin`. There are no hardcoded default passwords.

**First-time login:**
1. Navigate to `http://Originalelectronics.local`
2. Log in with the admin credentials created in Step 8
3. Go to **Admin → Settings** to configure the company name, logo, and tax rate
4. Go to **Products** to add your inventory

---

## Admin Guide

### Accessing Settings

Navigate to **Admin (shield icon) → Settings** in the sidebar.

### System Settings

| Setting | Description |
|---|---|
| Company Name / Address / Phone | Displayed on receipts and reports |
| Company Logo | PNG/JPG/WEBP — appears on receipts, reports, and the sidebar |
| Currency Symbol | Displayed on all price fields |
| Tax Rate | Decimal (e.g. `0.15` = 15%) |
| Exchange Rate | 1 USD = X SLSH; snapshotted per sale |
| Receipt Header / Footer | Text printed on thermal and PDF receipts |
| Barcode Prefix / Padding | Controls auto-generated barcode format |
| Label Options | Toggle price, SKU, and company name on printed labels |

### Server Shutdown (Admin Only)

The **Settings** page contains a **Server Control** section at the bottom (red border — danger zone).

**To shut down the server:**
1. Open **Admin → Settings**
2. Scroll to the **System Administration — Danger Zone** section
3. Click **Shutdown Server**
4. Read the confirmation dialog carefully
5. Click **Yes, Shutdown** to confirm

**What happens next:**
- The shutdown API endpoint logs the event (user, timestamp, IP address)
- A 2-second delay allows the confirmation response to reach the browser
- The Waitress server stops and closes all connections
- The browser displays: *"Server has been stopped. Close this tab."*
- The server must be restarted manually (see [Server Management](#server-management))

> ⚠️ Only users with the **Admin** role can see and use the shutdown button.
> The endpoint is rate-limited to **1 call per 30 seconds** and fully logged in the Audit Log.

### Audit Log

All sensitive actions — settings changes, user creation, shutdown requests — are recorded in the **Admin → Audit Log** (`/admin/logs`).

---

## Server Management

### Starting the Server

| Method | Command / Action |
|---|---|
| Desktop shortcut | Double-click **"Original Electronics"** on Desktop |
| VBScript (silent) | Double-click `launcher.vbs` |
| Batch file | Run `start_server.bat` |
| Terminal | `python server.py` |

### Stopping the Server

| Method | Notes |
|---|---|
| **In-app shutdown button** | Settings → Server Control → Shutdown Server (recommended) |
| `stop_server.bat` | Finds and kills the process on port 80 |
| `Ctrl+C` in terminal | Only works if `server.py` was started in a visible terminal |

### Viewing Server Logs

Logs are written to `logs/server.log` with automatic rotation (5 MB per file, 3 backups retained):

```
logs/
└── server.log          ← current log
    server.log.1        ← previous rotation
    server.log.2
    server.log.3
```

### Server Configuration

| Parameter | Default | Set via |
|---|---|---|
| Host | `0.0.0.0` (all interfaces) | Hard-coded in `server.py` |
| Port | `80` | `PORT` env variable |
| Worker threads | `8` | `server.py` → `threads=8` |
| Channel timeout | `120 s` | `server.py` → `channel_timeout=120` |
| Connection limit | `500` | `server.py` → `connection_limit=500` |
| Log rotation | 5 MB / 3 backups | `server.py` → `RotatingFileHandler` |

---

## Project Structure

```
electronics_pos/
│
├── server.py                   # Waitress production entry point + shutdown mechanism
├── run.py                      # Flask dev server entry point (localhost:5000)
├── config.py                   # Config classes: Dev / Prod / Test
├── requirements.txt            # All Python dependencies
├── .env.example                # Environment variable template
│
├── setup_hosts.bat             # (Run once as Admin) Adds Originalelectronics.local to hosts
├── start_server.bat            # Hidden-window launcher (called by launcher.vbs)
├── launcher.vbs                # Silent VBScript wrapper — zero terminal flash
├── create_shortcut.bat         # Creates "Original Electronics" Desktop shortcut
├── stop_server.bat             # Kills the Waitress process on port 80
│
├── app/
│   ├── __init__.py             # App factory: create_app(), extensions, blueprints
│   ├── models.py               # All SQLAlchemy models (User, Product, Sale, …)
│   ├── decorators.py           # @role_required() access control decorator
│   ├── forms.py                # WTForms form classes
│   ├── context_processors.py   # Global template context (company_name, currency, …)
│   │
│   ├── routes/
│   │   ├── auth.py             # /auth/  — Login / logout
│   │   ├── main.py             # /       — Dashboard
│   │   ├── pos.py              # /pos/   — POS terminal + checkout API
│   │   ├── products.py         # /products/ — Inventory CRUD, barcodes, labels
│   │   ├── sales.py            # /sales/ — History, receipts, reports
│   │   ├── customers.py        # /customers/ — CRM, ledger, payments
│   │   ├── returns.py          # /sales/ — Returns & voids (shares URL prefix)
│   │   ├── expenses.py         # /expenses/ — Expense tracking
│   │   ├── admin.py            # /admin/ — Users, settings, shutdown API
│   │   └── api.py              # /api/   — AJAX / REST endpoints
│   │
│   ├── services/
│   │   ├── audit_service.py    # AuditLog write/read helpers
│   │   ├── currency_service.py # Exchange rate helpers (get_rate, to_usd)
│   │   ├── barcode_service.py  # Auto-barcode generation, image rendering
│   │   └── label_service.py    # PDF and ZPL label generation
│   │
│   ├── templates/              # Jinja2 HTML templates
│   │   ├── base.html           # Master layout (sidebar, nav, notifications bell)
│   │   ├── admin/              # Admin panel templates (settings.html, users.html, …)
│   │   ├── pos/                # POS terminal templates
│   │   ├── products/           # Inventory templates + label print templates
│   │   ├── sales/              # Sales history, receipts, reports (inc. PDF versions)
│   │   ├── customers/          # CRM templates
│   │   ├── expenses/           # Expense templates
│   │   └── …
│   │
│   └── static/
│       ├── css/                # style.css, pos.css
│       ├── js/                 # pos.js, payment.js
│       └── uploads/logos/      # Uploaded company logos (auto-created)
│
├── migrations/                 # Alembic migration scripts
├── tests/                      # pytest test suite
│   ├── conftest.py             # Fixtures: app, client, users, products, sales
│   ├── test_auth.py
│   ├── test_returns.py
│   └── …
│
└── logs/
    └── server.log              # Auto-created by server.py on first run
```

---

## Useful CLI Commands

```bash
# Start the application
python server.py                # Production (Waitress, port 80)
python run.py                   # Development (Flask dev server, port 5000)

# Database
flask db upgrade                # Apply pending migrations
flask db migrate -m "message"   # Generate a migration after model changes

# User management
flask create-admin              # Create an admin user interactively
flask init-db                   # Create all tables without migrations
flask seed-data                 # Populate sample/demo data
flask reset-password            # Reset a user's password interactively
flask list-users                # List all users and their roles

# Testing
pytest                          # Run all tests
pytest --cov=app                # Run with coverage report
pytest tests/test_auth.py -v    # Run a specific test file (verbose)
```

---

## Troubleshooting

### "Port 80 already in use"

Another application (IIS, Apache, Skype, etc.) is using port 80.

```bash
# Find which process is using port 80
netstat -ano | findstr :80

# Kill the process (replace PID with the actual PID)
taskkill /PID <PID> /F
```

Or change the port by setting `PORT=8080` in `.env` and restarting.

---

### "Originalelectronics.local not resolving"

The hosts file entry is missing or was removed.

Re-run `setup_hosts.bat` **as Administrator**. If the problem persists, manually verify
`C:\Windows\System32\drivers\etc\hosts` contains:

```
127.0.0.1    Originalelectronics.local
```

---

### "Permission denied" when starting on port 80

Port 80 is a privileged port on Windows. Run the terminal or the launcher as **Administrator**:
right-click `launcher.vbs` → **Run as administrator**.

---

### "Server won't start — Python error on launch"

1. Check `logs\server.log` for the full traceback
2. Ensure the virtual environment is activated (`venv\Scripts\activate`)
3. Verify all dependencies are installed: `pip install -r requirements.txt`
4. Confirm `FLASK_ENV` and `DATABASE_URL` are set correctly in `.env`
5. Ensure MySQL is running: `net start MySQL80` (or your service name)

---

### "Browser didn't open automatically"

The server may have taken longer than 3 seconds to start. Manually navigate to:
`http://Originalelectronics.local`

---

### "Shutdown button not visible in Settings"

Only users with the **Admin** role see the Server Control section. Log in as an Admin
and navigate to **Admin → Settings**.

---

### "PDF generation fails / blank PDFs"

- Confirm wkhtmltopdf is installed at `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`
- Or set the correct path in `.env`: `WKHTMLTOPDF_PATH=C:\path\to\wkhtmltopdf.exe`
- Verify: `"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe" --version`

---

### "`flask db upgrade` fails with 'Table already exists'"

The database has tables from a manual setup. Mark the current schema as up-to-date:

```bash
flask db stamp head
```

---

### "Barcode images not generating"

Pillow (PIL) is required for PNG barcode output. Reinstall dependencies:

```bash
pip install --upgrade Pillow
```

---

## License

Proprietary — Developed for **Original Electronics**. All rights reserved.
