import sqlite3
import pandas as pd

conn = sqlite3.connect('data/ipl.db')

print("2023 delivery match_ids (first 30):")
result = pd.read_sql("SELECT DISTINCT match_id FROM deliveries WHERE season=2023 ORDER BY match_id LIMIT 30", conn)
print(result)

print(f"\nTotal unique 2023 delivery match_ids: {pd.read_sql('SELECT COUNT(DISTINCT match_id) as cnt FROM deliveries WHERE season=2023', conn).iloc[0,0]}")

print("\n2023 matches match_ids (first 10):")
result = pd.read_sql("SELECT DISTINCT match_id FROM matches WHERE season=2023 ORDER BY match_id LIMIT 10", conn)
print(result)

print("\nChecking if all 2023 match_ids from matches table exist in deliveries:")
all_matches = set(pd.read_sql("SELECT DISTINCT match_id FROM matches WHERE season=2023", conn)['match_id'].tolist())
all_deliveries = set(pd.read_sql("SELECT DISTINCT match_id FROM deliveries WHERE season=2023", conn)['match_id'].tolist())

matches_not_in_deliveries = all_matches - all_deliveries
deliveries_not_in_matches = all_deliveries - all_matches

if matches_not_in_deliveries:
    print(f"Matches without deliveries: {matches_not_in_deliveries}")
else:
    print("All matches have deliveries")

if deliveries_not_in_matches:
    print(f"Deliveries without match metadata: {len(deliveries_not_in_matches)} unique match_ids")
    print(f"Sample: {list(deliveries_not_in_matches)[:5]}")
else:
    print("All deliveries have match metadata")

conn.close()
