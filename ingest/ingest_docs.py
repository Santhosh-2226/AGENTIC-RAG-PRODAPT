import sqlite3
import pandas as pd

DB_PATH = "data/ipl.db"

with sqlite3.connect(DB_PATH) as conn:
    # List all tables
    tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
    print("Tables in database:")
    print(tables)
    
    # View sample data from each table
    for table in tables['name']:
        print(f"\n--- {table.upper()} ---")
        df = pd.read_sql(f"SELECT * FROM {table} LIMIT 5", conn)
        print(df)
        print(f"Total rows: {len(pd.read_sql(f'SELECT * FROM {table}', conn))}")