import pandas as pd
from pathlib import Path

BASE_DIR = Path.cwd()
RAW_DIR = BASE_DIR / "data" / "raw"

# Load 2022 matches
df_2022 = pd.read_csv(RAW_DIR / "IPL_Matches_2022.csv")
print("2022 Matches - Original:")
print(f"  Shape: {df_2022.shape}")
print(f"  Columns: {list(df_2022.columns[:8])}")
print(f"  ID values (first 3): {df_2022['ID'].head(3).tolist()}")

# Load 2023 matches
df_2023 = pd.read_csv(RAW_DIR / "each_match_records-2023.csv")
print("\n2023 Matches - Original:")
print(f"  Shape: {df_2023.shape}")
print(f"  Columns: {list(df_2023.columns[:8])}")
print(f"  match_number (first 3): {df_2023['match_number'].head(3).tolist()}")
print(f"  Has 'ID' column: {'ID' in df_2023.columns}")

# Standardize columns on both
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

df_2022_std = standardize_columns(df_2022)
df_2023_std = standardize_columns(df_2023)

print("\n2022 after standardize - first 5 cols:", list(df_2022_std.columns[:5]))
print("2023 after standardize - first 5 cols:", list(df_2023_std.columns[:5]))

# Add season if missing
df_2022_std['season'] = 2022
df_2023_std['season'] = 2023

print("\n2022 has 'id' column:", 'id' in df_2022_std.columns)
print("2023 has 'id' column:", 'id' in df_2023_std.columns)
print("2023 has 'match_number' column:", 'match_number' in df_2023_std.columns)

# Concat
combined = pd.concat([df_2022_std, df_2023_std], ignore_index=True, sort=False)
print(f"\nCombined before drop_duplicates: {combined.shape}")

# Drop duplicates
combined_dedup = combined.drop_duplicates()
print(f"Combined after drop_duplicates: {combined_dedup.shape}")

# Now run normalize_matches logic
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

df_renamed = combined_dedup.rename(columns={k: v for k, v in rename_map.items() if k in combined_dedup.columns})
print(f"\nAfter rename - has 'match_id': {'match_id' in df_renamed.columns}")
print(f"After rename - has 'match_number': {'match_number' in df_renamed.columns}")

# See which rows would be kept
keep_cols = [c for c in [
    "match_id", "season", "date", "venue", "team1", "team2",
    "toss_winner", "toss_decision", "winner",
    "win_by_runs", "win_by_wickets", "player_of_match"
] if c in df_renamed.columns]

print(f"\nKeep columns: {keep_cols}")
print(f"'match_id' in keep_cols: {'match_id' in keep_cols}")

# Try to create match_id if missing
if "match_id" not in df_renamed.columns:
    print("\nmatch_id not found, creating from match_number...")
    if "match_number" in df_renamed.columns:
        df_renamed["match_id"] = df_renamed["season"].astype(str) + "_" + df_renamed["match_number"].astype(str)
        print(f"Created match_id from season + match_number")
        print(f"Sample match_ids: {df_renamed['match_id'].head(10).tolist()}")
    else:
        print("ERROR: No match_number column either!")

# Now check what we'd save
keep_cols_final = [c for c in [
    "match_id", "season", "date", "venue", "team1", "team2",
    "toss_winner", "toss_decision", "winner",
    "win_by_runs", "win_by_wickets", "player_of_match"
] if c in df_renamed.columns]

print(f"\nFinal keep_cols: {keep_cols_final}")

result = df_renamed[keep_cols_final].drop_duplicates(subset=["match_id"])
print(f"\nFinal result shape: {result.shape}")
print(f"2022 matches: {len(result[result['season']==2022])}")
print(f"2023 matches: {len(result[result['season']==2023])}")
