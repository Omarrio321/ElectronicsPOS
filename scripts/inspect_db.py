import os
import sqlalchemy
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()

# Get DB URL from env
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print("DATABASE_URL not found in environment")
    exit(1)

print(f"Connecting to: {db_url}")
engine = create_engine(db_url)
inspector = inspect(engine)

try:
    params = inspector.get_table_names()
    print("Tables found:", params)
    
    for table in params:
        print(f"\n--- {table} ---")
        columns = inspector.get_columns(table)
        for col in columns:
            print(f"  Col: {col['name']} ({col['type']})")
            
        indexes = inspector.get_indexes(table)
        for idx in indexes:
            print(f"  Idx: {idx['name']} - {idx['column_names']} unique={idx['unique']}")
            
        fks = inspector.get_foreign_keys(table)
        for fk in fks:
            print(f"  FK: {fk['name']} -> {fk['referred_table']}.{fk['referred_columns']}")

except Exception as e:
    print(f"Error inspecting DB: {e}")
