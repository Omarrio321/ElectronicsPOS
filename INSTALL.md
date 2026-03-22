# Electronics POS — Installation Guide

Step-by-step guide for setting up the POS system on a Windows PC.

---

## Prerequisites

Install these before continuing:

| Software | Version | Download |
|----------|---------|----------|
| Python | 3.11 or newer | https://www.python.org/downloads/ |
| MySQL | 8.0 or newer | https://dev.mysql.com/downloads/mysql/ |
| wkhtmltopdf | latest | https://wkhtmltopdf.org/downloads.html |

> **wkhtmltopdf install path:** Accept the default `C:\Program Files\wkhtmltopdf\`. The app looks for it there automatically.

---

## Step 1 — Get the Project Files

Extract the project ZIP (or clone the repository) into a folder, for example:

```
C:\POS\electronics_pos\
```

Open **Command Prompt** and navigate there:

```cmd
cd C:\POS\electronics_pos
```

---

## Step 2 — Create a Virtual Environment

```cmd
python -m venv venv
venv\Scripts\activate
```

Your prompt should now start with `(venv)`.

---

## Step 3 — Install Dependencies

```cmd
pip install -r requirements.txt
```

This installs Flask, SQLAlchemy, and all required packages including `waitress` (the Windows production server).

---

## Step 4 — Configure the Environment

Copy the example config file:

```cmd
copy .env.example .env
```

Open `.env` in Notepad and fill in your values:

```
SECRET_KEY=<generate one — see below>
ADMIN_PASSWORD=<choose a strong admin password>
DATABASE_URL=mysql+pymysql://pos_user:your_db_password@localhost:3306/electronics_pos
DB_HOST=localhost
DB_NAME=electronics_pos
DB_USER=pos_user
DB_PASSWORD=your_db_password
FLASK_ENV=production
```

**Generate a SECRET_KEY:**

```cmd
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and paste it as the `SECRET_KEY` value.

---

## Step 5 — Set Up the MySQL Database

Open **MySQL Command Line Client** (installed with MySQL) and run:

```sql
CREATE DATABASE electronics_pos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'pos_user'@'localhost' IDENTIFIED BY 'your_db_password';
GRANT ALL PRIVILEGES ON electronics_pos.* TO 'pos_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Replace `your_db_password` with the same password you put in `.env`.

---

## Step 6 — Run Database Migrations

Back in Command Prompt (with venv active):

```cmd
set FLASK_ENV=production
flask db upgrade
```

This creates all database tables. You should see output ending with `Running upgrade ... -> ...`.

---

## Step 7 — Create the Admin Account

```cmd
flask create-admin
```

Follow the prompts to set the admin username and password. Use the same password you set as `ADMIN_PASSWORD` in `.env`, or choose a new one.

---

## Step 8 — Launch the POS

Double-click **`start_pos.bat`** in the project folder.

A Command Prompt window will open showing:

```
Starting Electronics POS System...
Serving on http://0.0.0.0:5000
```

---

## Step 9 — Open in Browser

On the same PC:

```
http://localhost:5000
```

From any phone or tablet on the same Wi-Fi network:

```
http://<PC's IP address>:5000
```

To find the PC's IP: open Command Prompt and type `ipconfig`. Look for the IPv4 Address.

---

## Step 10 — Configure Company Info

1. Log in with the admin account you created.
2. Go to **Admin → Settings**.
3. Set your company name, address, phone number, and currency.
4. Upload a company logo if desired (shown on receipts and reports).

---

## Daily Backup

Double-click **`backup_db.bat`** to create a backup of the database.

Backups are saved to the `backups\` folder with a timestamp in the filename (e.g. `pos_backup_20260311_1430.sql`).

**Restore from backup:** double-click **`restore_db.bat`** and enter the backup filename when prompted.

---

## Automated Startup and Backup (Windows Task Scheduler)

### Auto-start POS at login

1. Open **Task Scheduler** (search in Start menu).
2. Click **Create Basic Task**.
3. Name: `Start POS System`
4. Trigger: **When I log on**
5. Action: **Start a program**
6. Program: `C:\POS\electronics_pos\start_pos.bat`
7. Click **Finish**.

### Auto-backup daily at 11 PM

1. Click **Create Basic Task**.
2. Name: `POS Daily Backup`
3. Trigger: **Daily**, set time to `11:00 PM`
4. Action: **Start a program**
5. Program: `C:\POS\electronics_pos\backup_db.bat`
6. Click **Finish**.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ERROR: Virtual environment not found` | Run Step 2 again |
| `ERROR: .env file not found` | Run `copy .env.example .env` and fill in values |
| `Access denied for user 'pos_user'@'localhost'` | Re-run the MySQL GRANT commands in Step 5 |
| PDF reports are blank or fail | Verify wkhtmltopdf is installed at `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe` |
| App starts but shows 500 errors | Check that `flask db upgrade` completed without errors (Step 6) |
| Can't access from phone | Make sure the PC firewall allows port 5000 (Windows Defender → Allow an app → add `waitress-serve`) |

---

## Updating to a New Version

1. Stop the POS (close the `start_pos.bat` window).
2. Take a backup: double-click `backup_db.bat`.
3. Replace the project files with the new version.
4. With venv active, run: `pip install -r requirements.txt`
5. Run: `flask db upgrade`
6. Start the POS: double-click `start_pos.bat`.
