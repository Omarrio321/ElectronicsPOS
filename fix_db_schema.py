from app import create_app, db
from sqlalchemy import text
from dotenv import load_dotenv
import os

load_dotenv()

app = create_app()

with app.app_context():
    try:
        # Detect DB type to be safe, though error said pymysql
        uri = app.config['SQLALCHEMY_DATABASE_URI']
        print(f"Connecting to: {uri}")
        
        if 'mysql' in uri:
            print("Detected MySQL/MariaDB. Altering table...")
            # MySQL syntax
            db.session.execute(text("ALTER TABLE payment MODIFY sale_id INT NULL;"))
            db.session.commit()
            print("Successfully made payment.sale_id nullable.")
        elif 'sqlite' in uri:
            print("Detected SQLite. Migration is harder (requires table rebuild).")
            # SQLite doesn't support MODIFY COLUMN directly usually, but logic below handles check
            print("Skipping SQLite auto-fix in this script to avoid data loss risks without full migration tool.")
        else:
            print("Unknown DB type. Attempting generic ALTER...")
            db.session.execute(text("ALTER TABLE payment ALTER COLUMN sale_id DROP NOT NULL;")) # Postgres style
            db.session.commit()
            
    except Exception as e:
        print(f"Error: {e}")
