import pandas as pd
from pathlib import Path

BASE_DIR = Path.cwd()
RAW_DIR = BASE_DIR / "data" / "raw"

def standardize_columns(df):
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
        .str.replace("/", "_", regex=False)
        .str.replace(r"[^a-z0-9_]", "", regex=True)
    )
    return df

# Load and process
df_2022 = pd.read_csv(RAW_DIR / "IPL_Matches_2022.csv")
df_2023 = pd.read_csv(RAW_DIR / "each_match_records-2023.csv")

df_2022 = standardize_columns(df_2022)
df_2023 = standardize_columns(df_2023)

df_2022['season'] = 2022
df_2023['season'] = 2023

combined = pd.concat([df_2022, df_2023], ignore_index=True, sort=False)
combined = combined.drop_duplicates()

# Rename
rename_map = {
    "id": "match_id",
    "matchid": "match_id",
    "match_no": "match_number",
    "matchnumber": "match_number",
    "team_1": "team1",
    "team_2": "team2",
    "match_date": "date",
    "toss_won": "toss_winner",
    "winning_team": "winner",
}

df = combined.rename(columns={k: v for k, v in rename_map.items() if k in combined.columns})

print("After rename:")
print(f"  2022 match_id (first 3): {df[df['season']==2022]['match_id'].head(3).values.tolist()}")
print(f"  2023 match_id (first 3): {df[df['season']==2023]['match_id'].head(3).values.tolist()}")
if 'match_number' in df.columns:
    print(f"  2022 match_number (first 3): {df[df['season']==2022]['match_number'].head(3).values.tolist()}")
    print(f"  2023 match_number (first 3): {df[df['season']==2023]['match_number'].head(3).values.tolist()}")
else:
    print("  match_number column not found")

# Now check for duplicates in match_id BEFORE creating new ones
print("\nBefore dedup on match_id:")
print(f"  Total rows: {len(df)}")
print(f"  Unique match_ids: {df['match_id'].nunique()}")
print(f"  Duplicate match_ids: {(df['match_id'].duplicated().sum())}")

# Check what matches have duplicate IDs
dupes = df[df['match_id'].duplicated(keep=False)].sort_values('match_id')[['match_id', 'season', 'team1', 'team2']]
if len(dupes) > 0:
    print(f"\n  Duplicate match_ids:")
    print(dupes.head(10))

# Now do drop_duplicates
df_dedup = df.drop_duplicates(subset=['match_id'])
print(f"\nAfter drop_duplicates(subset=['match_id']):")
print(f"  Total rows: {len(df_dedup)}")
print(f"  2022 rows: {len(df_dedup[df_dedup['season']==2022])}")
print(f"  2023 rows: {len(df_dedup[df_dedup['season']==2023])}")

# Check which 2023 rows were kept
if len(df_dedup[df_dedup['season']==2023]) > 0:
    kept_2023 = df_dedup[df_dedup['season']==2023][['match_id', 'season', 'team1', 'team2']]
    print(f"\n  2023 row kept:")
    print(kept_2023)
