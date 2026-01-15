import os
import sqlalchemy
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print("DATABASE_URL not found!")
    exit(1)

print(f"Connecting to {db_url}...")
engine = create_engine(db_url)

with engine.connect() as conn:
    print("Disabling Foreign Key Checks...")
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    
    # Get all tables
    inspector = sqlalchemy.inspect(engine)
    tables = inspector.get_table_names()
    
    if not tables:
        print("No tables found to drop.")
    else:
        print(f"Found tables: {tables}")
        for table in tables:
            print(f"Dropping table {table}...")
            conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
            
    print("Re-enabling Foreign Key Checks...")
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    conn.commit()
    print("Database cleaned successfully!")
