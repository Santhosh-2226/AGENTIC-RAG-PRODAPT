import pandas as pd
from pathlib import Path

BASE_DIR = Path.cwd()
RAW_DIR = BASE_DIR / "data" / "raw"

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
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

def add_season_if_missing(df: pd.DataFrame, filename: str) -> pd.DataFrame:
    df = df.copy()
    if "season" not in df.columns:
        if "2023" in filename:
            df["season"] = 2023
        elif "2022" in filename:
            df["season"] = 2022
    return df

# Load 2022 matches
df_2022 = pd.read_csv(RAW_DIR / "IPL_Matches_2022.csv")
df_2022 = standardize_columns(df_2022)
df_2022 = add_season_if_missing(df_2022, "IPL_Matches_2022.csv")

# Load 2023 matches
df_2023 = pd.read_csv(RAW_DIR / "each_match_records-2023.csv")
df_2023 = standardize_columns(df_2023)
df_2023 = add_season_if_missing(df_2023, "each_match_records-2023.csv")

print(f"2022: {df_2022.shape}")
print(f"2023: {df_2023.shape}")

# Concat without drop_duplicates (as fixed)
combined = pd.concat([df_2022, df_2023], ignore_index=True, sort=False)
print(f"\nCombined: {combined.shape}")

# Now run normalize_matches logic
df = combined.copy()

rename_map = {
    "id": "raw_id",
    "matchid": "raw_id",
    "match_no": "match_number",
    "matchnumber": "match_number",
    "team_1": "team1",
    "team_2": "team2",
    "match_date": "date",
    "toss_won": "toss_winner",
    "winning_team": "winner",
    "won_by": "win_type",
    "margin": "win_margin",
    "man_of_match": "player_of_match",
    "winner_runs": "win_by_runs",
    "winner_wickets": "win_by_wickets",
}
df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
df = df.loc[:, ~df.columns.duplicated(keep='first')]

print(f"\nAfter rename: {df.shape}")

# Create match_id
if "raw_id" in df.columns:
    df.loc[df["season"] == 2022, "match_id"] = df.loc[df["season"] == 2022, "season"].astype(str) + "_" + df.loc[df["season"] == 2022, "raw_id"].astype(str)
if "match_number" in df.columns:
    df.loc[df["season"] == 2023, "match_id"] = df.loc[df["season"] == 2023, "season"].astype(str) + "_" + df.loc[df["season"] == 2023, "match_number"].astype(str)

print(f"\nAfter match_id creation:")
print(f"  2022 match_ids (first 3): {df[df['season']==2022]['match_id'].head(3).values.tolist()}")
print(f"  2023 match_ids (first 3): {df[df['season']==2023]['match_id'].head(3).values.tolist()}")
print(f"  Total unique match_ids: {df['match_id'].nunique()}")
print(f"  Match_id duplicates: {df['match_id'].duplicated().sum()}")

keep_cols = [c for c in [
    "match_id", "season", "date", "venue", "team1", "team2",
    "toss_winner", "toss_decision", "winner",
    "win_by_runs", "win_by_wickets", "player_of_match"
] if c in df.columns]

print(f"\nKeep cols: {keep_cols}")

df_final = df[keep_cols].drop_duplicates(subset=["match_id"])
print(f"\nFinal result: {df_final.shape}")
print(f"  2022 matches: {len(df_final[df_final['season']==2022])}")
print(f"  2023 matches: {len(df_final[df_final['season']==2023])}")
