import sqlite3
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
DB_PATH = BASE_DIR / "data" / "ipl.db"

MATCH_FILES = [
    "each_match_records-2023.csv",
    "IPL_Matches_2022.csv",
]

BALL_FILES = [
    "each_ball_records-2023.csv",
    "IPL_Ball_by_Ball_2022.csv",
]


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


def load_csvs(file_names: list[str]) -> pd.DataFrame:
    frames = []
    for file_name in file_names:
        file_path = RAW_DIR / file_name
        if not file_path.exists():
            print(f"Skipping missing file: {file_path}")
            continue

        df = pd.read_csv(file_path)
        df = standardize_columns(df)
        df = add_season_if_missing(df, file_name)
        frames.append(df)

        print(f"Loaded {file_name}: {df.shape[0]} rows, {df.shape[1]} columns")

    if not frames:
        raise FileNotFoundError("No CSV files were found in data/raw")

    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined = combined.drop_duplicates()
    return combined


def normalize_matches(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    rename_map = {
        "id": "raw_id",
        "matchid": "raw_id",
        "match_no": "match_number_field",
        "matchnumber": "matchnumber_field",
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

    def create_match_id(row):
        season = int(row['season'])
        if "raw_id" in row.index and pd.notna(row.get('raw_id')):
            try:
                return f"{season}_{int(row['raw_id'])}"
            except (ValueError, TypeError):
                pass
        for col in ["match_number", "match_number_field"]:
            if col in row.index and pd.notna(row.get(col)):
                try:
                    return f"{season}_{int(row[col])}"
                except (ValueError, TypeError):
                    pass
        return f"{season}_{row.name}"

    df["match_id"] = df.apply(create_match_id, axis=1)

    keep_cols = [c for c in [
        "match_id", "season", "date", "venue", "team1", "team2",
        "toss_winner", "toss_decision", "winner",
        "win_by_runs", "win_by_wickets", "player_of_match"
    ] if c in df.columns]

    if not keep_cols:
        raise ValueError("No usable match columns found after normalization.")

    df = df[keep_cols].drop_duplicates(subset=["match_id"])
    return df


def normalize_balls(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    rename_map = {
        "id": "raw_id",
        "matchid": "raw_id",
        "match_id": "raw_match_id",
        "match_no": "match_number_field",
        "matchnumber": "matchnumber_field",
        "innings": "inning",
        "overs": "over",
        "ballnumber": "ball",
        "batsman": "batter",
        "battingteam": "batting_team",
        "bowlingteam": "bowling_team",
        "totalrun": "total_runs",
        "total_run": "total_runs",
        "batsman_run": "batsman_runs",
        "extra_run": "extras",
        "extras_run": "extras",
        "iswicketdelivery": "is_wicket",
        "iswicKetdelivery": "is_wicket",
        "player_out": "player_dismissed",
        "kind": "wicket_type",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    df = df.loc[:, ~df.columns.duplicated(keep='first')]

    if "inning" not in df.columns and "innings" not in df.columns:
        df["inning"] = 1

    def create_match_id(row):
        season = int(row['season'])
        if "raw_id" in row.index and pd.notna(row.get('raw_id')):
            try:
                return f"{season}_{int(row['raw_id'])}"
            except (ValueError, TypeError):
                pass
        for col in ["match_number_field", "match_number"]:
            if col in row.index and pd.notna(row.get(col)):
                try:
                    return f"{season}_{int(row[col])}"
                except (ValueError, TypeError):
                    pass
        return f"{season}_{row.name}"

    df["match_id"] = df.apply(create_match_id, axis=1)

    keep_cols = [c for c in [
        "match_id", "season", "inning", "over", "ball",
        "batting_team", "bowling_team", "batter", "bowler",
        "batsman_runs", "extras", "total_runs",
        "is_wicket", "player_dismissed", "wicket_type"
    ] if c in df.columns]

    if not keep_cols:
        raise ValueError("No usable ball-by-ball columns found after normalization.")

    df = df[keep_cols].copy()

    for col in ["inning", "over", "ball", "batsman_runs", "extras", "total_runs", "is_wicket"]:
        if col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col].astype(str), errors="coerce").fillna(0)
            except Exception as e:
                print(f"Warning: Could not convert {col} to numeric: {e}")

    if "total_runs" not in df.columns or (df["total_runs"].sum() if "total_runs" in df.columns else 0) == 0:
        if "batsman_runs" in df.columns and "extras" in df.columns:
            df["total_runs"] = df["batsman_runs"] + df["extras"]
        elif "batsman_runs" in df.columns:
            df["total_runs"] = df["batsman_runs"]
        elif "extras" in df.columns:
            df["total_runs"] = df["extras"]

    return df


def build_batting_stats(balls_df: pd.DataFrame) -> pd.DataFrame:
    if "batter" not in balls_df.columns:
        return pd.DataFrame()

    grouped = (
        balls_df.groupby(["season", "batter"], dropna=False)
        .agg(
            runs=("batsman_runs", "sum"),
            balls_faced=("batter", "count"),
            innings=("match_id", "nunique"),
        )
        .reset_index()
    )
    grouped["strike_rate"] = (grouped["runs"] / grouped["balls_faced"] * 100).round(2)
    grouped = grouped.rename(columns={"batter": "player"})
    return grouped


def build_bowling_stats(balls_df: pd.DataFrame) -> pd.DataFrame:
    if "bowler" not in balls_df.columns:
        return pd.DataFrame()

    grouped = (
        balls_df.groupby(["season", "bowler"], dropna=False)
        .agg(
            balls_bowled=("bowler", "count"),
            runs_conceded=("total_runs", "sum"),
            wickets=("is_wicket", "sum"),
        )
        .reset_index()
    )
    grouped["overs"] = (grouped["balls_bowled"] / 6).round(1)
    grouped["economy"] = grouped.apply(
        lambda row: round(row["runs_conceded"] / row["overs"], 2) if row["overs"] else 0,
        axis=1,
    )
    grouped = grouped.rename(columns={"bowler": "player"})
    return grouped


def build_players_table(batting_df: pd.DataFrame, bowling_df: pd.DataFrame) -> pd.DataFrame:
    batting_players = batting_df[["season", "player"]].copy() if not batting_df.empty else pd.DataFrame(columns=["season", "player"])
    bowling_players = bowling_df[["season", "player"]].copy() if not bowling_df.empty else pd.DataFrame(columns=["season", "player"])
    players = pd.concat([batting_players, bowling_players], ignore_index=True).drop_duplicates()
    return players


def save_to_sqlite(matches_df: pd.DataFrame, balls_df: pd.DataFrame) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    batting_stats = build_batting_stats(balls_df)
    bowling_stats = build_bowling_stats(balls_df)
    players = build_players_table(batting_stats, bowling_stats)

    with sqlite3.connect(DB_PATH) as conn:
        matches_df.to_sql("matches", conn, if_exists="replace", index=False)
        balls_df.to_sql("deliveries", conn, if_exists="replace", index=False)
        batting_stats.to_sql("batting_stats", conn, if_exists="replace", index=False)
        bowling_stats.to_sql("bowling_stats", conn, if_exists="replace", index=False)
        players.to_sql("players", conn, if_exists="replace", index=False)

    print(f"\nSQLite database created at: {DB_PATH}")
    print(f"  matches      : {len(matches_df)} rows")
    print(f"  deliveries   : {len(balls_df)} rows")
    print(f"  batting_stats: {len(batting_stats)} rows")
    print(f"  bowling_stats: {len(bowling_stats)} rows")
    print(f"  players      : {len(players)} rows")


def main() -> None:
    print("Loading match files...")
    match_df_raw = load_csvs(MATCH_FILES)
    print("\nLoading ball-by-ball files...")
    balls_df_raw = load_csvs(BALL_FILES)

    print("\nNormalizing matches...")
    matches_df = normalize_matches(match_df_raw)
    print("Normalizing ball-by-ball data...")
    balls_df = normalize_balls(balls_df_raw)

    print("\nSaving to SQLite...")
    save_to_sqlite(matches_df, balls_df)
    print("\nDone. Run tools/query_data.py to verify.")


if __name__ == "__main__":
    main()