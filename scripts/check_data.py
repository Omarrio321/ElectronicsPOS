import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get('DATABASE_URL')
engine = create_engine(db_url)

singular = ['user', 'role', 'product', 'category', 'sale', 'sale_item', 'system_setting']
plural = ['users', 'roles', 'products', 'categories', 'sales', 'sale_items', 'system_settings']

with engine.connect() as conn:
    print("--- Singular Tables ---")
    for t in singular:
        try:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"{t}: {count}")
        except Exception as e:
            print(f"{t}: Error ({e})")

    print("\n--- Plural Tables ---")
    for t in plural:
        try:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            print(f"{t}: {count}")
        except Exception as e:
            print(f"{t}: Error ({e})")
