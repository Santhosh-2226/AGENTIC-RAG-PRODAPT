import sqlite3

conn = sqlite3.connect("data/ipl.db")
cur = conn.cursor()

# Find IPL 2023 winner (Final match)
cur.execute("""
    SELECT winner, match_type, date, team1, team2, margin, won_by
    FROM matches 
    WHERE season = 2023 AND match_type = 'Final'
""")
rows = cur.fetchall()
print("IPL 2023 Final:", rows)

# Also check what match_types exist
cur.execute("SELECT DISTINCT match_type FROM matches WHERE season=2023")
print("Match types 2023:", cur.fetchall())

# Most wins in 2023
cur.execute("""
    SELECT winner, COUNT(*) as wins 
    FROM matches 
    WHERE season=2023 AND winner != ''
    GROUP BY winner 
    ORDER BY wins DESC
""")
print("Wins per team 2023:", cur.fetchall())

conn.close()