import sqlite3
import pandas as pd

conn = sqlite3.connect('data/ipl.db')

print("=== DATABASE STATE ===")
print(f"Matches rows: {pd.read_sql('SELECT COUNT(*) as cnt FROM matches', conn).iloc[0,0]}")
print(f"Deliveries rows: {pd.read_sql('SELECT COUNT(*) as cnt FROM deliveries', conn).iloc[0,0]}")

print("\n=== DUPLICATE MATCHES ===")
dupes = pd.read_sql("""SELECT match_id, COUNT(*) as cnt FROM matches GROUP BY match_id HAVING COUNT(*) > 1""", conn)
if len(dupes) > 0:
    print(dupes.to_string(index=False))
else:
    print("No duplicates found")

print("\n=== MATCHES PER SEASON ===")
seasons = pd.read_sql("SELECT season, COUNT(*) as cnt FROM matches GROUP BY season", conn)
print(seasons.to_string(index=False))

print("\n=== FIRST 10 MATCH_IDS ===")
match_ids = pd.read_sql("SELECT match_id, season, date, team1, team2 FROM matches LIMIT 10", conn)
print(match_ids.to_string(index=False))

print("\n=== DELIVERIES MATCHES PER SEASON ===")
deliv_seasons = pd.read_sql("SELECT season, COUNT(DISTINCT match_id) as unique_matches, COUNT(*) as total_balls FROM deliveries GROUP BY season", conn)
print(deliv_seasons.to_string(index=False))

conn.close()
