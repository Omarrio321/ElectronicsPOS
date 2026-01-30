# ElectroPOS - Electronics Store POS System

A professional, feature-rich Point of Sale (POS) and Inventory Management system designed for electronics retailers. Built with Python, Flask, and a sleek, modern UI.

## 🚀 Key Features

### 🛒 Sales & POS
- **Interactive POS Terminal**: Quick product search, barcode ready, and intuitive cart management.
- **Local Payment Methods**: Integrated support for Cash, **Zaad**, and **E-Dahab** with iconic visual indicators.
- **Sale Detail Tracking**: Complete history of all transactions with easy navigation.
- **Export**: Generate professional PDF reports and Excel spreadsheets of your sales with date and cashier filtering.

### 📦 Inventory & Products
- **Inventory Management**:
    - Product tracking with SKU, Barcode, and Stock Levels.
    - Low stock alerts and categorization.
    - **Export**: Generate professional PDF reports and Excel spreadsheets of your inventory with selective filtering.
- **Product Gallery**: Professional display of products with detailed information.

### 💰 Expense Management
- **Comprehensive Tracking**: Manage business costs, categorize expenses (Rent, Utilities, Maintenance), and track payment status (Paid/Pending).
- **Insightful Visuals**: Built-in charts (Chart.js) showing expense distribution by category.
- **Net Profit Calculation**: Automatically integrates with sales data to provide a real-time view of business health.

### 📊 Reporting & Exports
- **Dynamic PDF Generation**: Export professional PDF receipts, sales history summaries, and comprehensive business reports.
- **Excel Exports**: Download Sales, Inventory, and Reports data as styled Excel spreadsheets for further analysis.
- **Multi-Sheet Reports**: Export comprehensive report workbooks with Summary, Daily Sales, Top Products, and Cashier Performance sheets.
- **Visual Dashboards**: Track revenue, sales volume, and top-performing products at a glance.

## 🛠️ Technology Stack

- **Backend**: Python 3.x, Flask
- **Database**: MySQL (via SQLAlchemy & PyMySQL)
- **Frontend**: Bootstrap 5.3 (Vanilla CSS + HTML5), Font Awesome 6.0
- **Analytics**: Chart.js for data visualization
- **PDF Core**: wkhtmltopdf + pdfkit

## ⚙️ Installation & Setup

### 1. Requirements
- Python 3.8+
- MySQL Server
- **wkhtmltopdf**: Required for PDF generation.
  - Install from [wkhtmltopdf.org](https://wkhtmltopdf.org/downloads.html).
  - Default path expected: `C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe`

### 2. Setup Procedure
```bash
# Clone the repository
git clone https://github.com/Omarrio321/ElectronicsPOS.git
cd ElectronicsPOS

# Create a virtual environment
python -m venv venv
.\venv\Scripts\activate

flask run

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory:
```env
SECRET_KEY=your-secret-key
DATABASE_URL=mysql+pymysql://user:password@localhost/ElectroPOS
ADMIN_PASSWORD=your-secure-password
```

### 4. Database Setup
```bash
flask db upgrade
python scripts/seed_admin.py
```

### 5. Running the Application
```bash
flask run
```
Access the application at `http://localhost:5000`.

## 📜 License
MIT License - Developed for professional business management.