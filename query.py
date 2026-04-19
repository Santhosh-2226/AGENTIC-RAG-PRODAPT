import pandas as pd
import sqlite3
conn = sqlite3.connect("data/ipl.db")
for table in ["matches", "deliveries", "batting_stats", "bowling_stats", "players"]:
    df = pd.read_sql(f"SELECT * FROM {table}", conn)
    print(f"{table}: {len(df)} rows")
    print(f"  2022: {len(df[df['season'] == 2022])} rows, 2023: {len(df[df['season'] == 2023])} rows")
conn.close()
