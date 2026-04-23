import sqlite3
import os

# Find your database file
db_path = None
for root, dirs, files in os.walk("."):
    for f in files:
        if f.endswith(".db"):
            print("Found DB:", os.path.join(root, f))
            db_path = os.path.join(root, f)

if not db_path:
    print("No .db file found!")
else:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Show all tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    print("\nTables:", [t[0] for t in tables])
    
    # Show columns for each table
    for table in tables:
        cur.execute(f"PRAGMA table_info({table[0]})")
        cols = [c[1] for c in cur.fetchall()]
        print(f"\n{table[0]} columns:", cols)
    
    # Try to find winner info
    print("\n--- Sample matches rows ---")
    try:
        cur.execute("SELECT * FROM matches WHERE season=2023 LIMIT 5")
        rows = cur.fetchall()
        for r in rows:
            print(r)
    except Exception as e:
        print("matches query failed:", e)
    
    conn.close()