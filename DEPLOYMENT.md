# Electronics POS - Deployment Checklist

## Pre-Deployment Requirements

### 1. Environment Setup
- [ ] Create production `.env` file from `.env.example`
- [ ] Generate secure `SECRET_KEY` using `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Set strong `ADMIN_PASSWORD`
- [ ] Configure `DATABASE_URL` for production MySQL server

### 2. MySQL Database Setup
```sql
-- Create production database
CREATE DATABASE electronics_pos CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create application user (recommended)
CREATE USER 'pos_user'@'localhost' IDENTIFIED BY 'secure_password_here';
GRANT ALL PRIVILEGES ON electronics_pos.* TO 'pos_user'@'localhost';
FLUSH PRIVILEGES;

-- Create test database (for CI/CD)
CREATE DATABASE electronics_pos_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON electronics_pos_test.* TO 'pos_user'@'localhost';
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Database Migrations
```bash
flask db upgrade
```

### 5. Run Tests
```bash
# All tests
pytest

# With coverage report
pytest --cov=app --cov-report=html

# Only unit tests (fast)
pytest -m unit

# Only integration tests
pytest -m integration
```

---

## Production Deployment

### Windows (Local Shop PC) — RECOMMENDED
```batch
REM Double-click start_pos.bat, OR run manually:
set FLASK_ENV=production
waitress-serve --port=5000 --threads=4 --call "app:create_app"
```

For LAN access from phones/tablets on the same network:
```batch
waitress-serve --port=5000 --host=0.0.0.0 --threads=4 --call "app:create_app"
```
Then access from any device: `http://YOUR_PC_IP:5000` (find IP with `ipconfig`)

**Note:** `gunicorn` does NOT run on Windows. Use `waitress` only on Windows.

### Linux / VPS Deployment
```bash
# Production (Linux)
export FLASK_ENV=production
gunicorn --workers 4 --bind 0.0.0.0:5000 "app:create_app()"
```

### Development (localhost only)
```bash
python run.py
# Binds to 127.0.0.1:5000 only
```

### Nginx Reverse Proxy (Linux VPS only)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /path/to/electronics_pos/app/static;
        expires 1y;
    }
}
```

### Automated Startup (Windows Task Scheduler)
1. Open Task Scheduler (`taskschd.msc`)
2. Create Basic Task → "Start Electronics POS"
3. Trigger: "When I log on"
4. Action: Start Program → `C:\path\to\electronics_pos\start_pos.bat`
5. Check "Run with highest privileges"

### Automated Daily Backup (Windows Task Scheduler)
1. Create Basic Task → "POS Database Backup"
2. Trigger: Daily at 11:00 PM
3. Action: Start Program → `C:\path\to\electronics_pos\backup_db.bat`
4. Add argument: `/silent` (optional — the script pauses at the end for manual use)

**Backup files are saved to:** `electronics_pos\backups\`
**Restore:** Double-click `restore_db.bat` and follow prompts

---

## Security Checklist

- [ ] `SECRET_KEY` is randomly generated and not committed to version control
- [ ] `DEBUG=False` in production
- [ ] HTTPS enabled (SSL certificate installed)
- [ ] `SESSION_COOKIE_SECURE=True` in production
- [ ] Database user has minimal required permissions
- [ ] Firewall configured (only ports 80/443 exposed)
- [ ] Regular database backups configured

---

## Post-Deployment Verification

1. [ ] Login as admin works
2. [ ] POS search and cart operations work
3. [ ] Checkout creates sales correctly
4. [ ] Reports load without errors
5. [ ] Low stock alerts display correctly
6. [ ] PDF receipts generate (requires wkhtmltopdf)
7. [ ] Offline mode works (disconnect internet, UI still loads)
