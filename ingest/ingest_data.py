import re
import sqlite3
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
DB_PATH = BASE_DIR / "data" / "ipl.db"

BALL_2023_PATH = RAW_DIR / "each_ball_records-2023.csv"
MATCH_2023_PATH = RAW_DIR / "each_match_records-2023.csv"
BALL_2022_PATH = RAW_DIR / "IPL_Ball_by_Ball_2022.csv"
MATCH_2022_PATH = RAW_DIR / "IPL_Matches_2022.csv"


TEAM_NAME_MAP = {
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
}

PLAYER_NAME_MAP = {
    "V Kohli": "Virat Kohli",
    "F du Plessis": "Faf du Plessis",
    "GJ Maxwell": "Glenn Maxwell",
    "KD Karthik": "Dinesh Karthik",
    "MK Lomror": "Mahipal Lomror",
    "HV Patel": "Harshal Patel",
    "JR Hazlewood": "Josh Hazlewood",
    "JC Buttler": "Jos Buttler",
    "SV Samson": "Sanju Samson",
    "YBK Jaiswal": "Yashasvi Jaiswal",
    "R Ashwin": "Ravichandran Ashwin",
    "M Prasidh Krishna": "Prasidh Krishna",
    "HH Pandya": "Hardik Pandya",
    "WP Saha": "Wriddhiman Saha",
    "DA Miller": "David Miller",
    "R Sai Kishore": "Sai Kishore",
    "LH Ferguson": "Lockie Ferguson",
    "TA Boult": "Trent Boult",
    "YS Chahal": "Yuzvendra Chahal",
    "MS Wade": "Matthew Wade",
    "R Tewatia": "Rahul Tewatia",
}


def clean_text(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)
    return value if value else None


def clean_team_name(value):
    value = clean_text(value)
    if value is None:
        return None
    return TEAM_NAME_MAP.get(value, value)


def clean_player_name(value):
    value = clean_text(value)
    if value is None:
        return None
    return PLAYER_NAME_MAP.get(value, value)


def parse_2023_batsman_runs(outcome):
    outcome = clean_text(outcome)
    if outcome is None:
        return 0

    outcome_lower = outcome.lower()

    if outcome_lower == "w":
        return 0

    if "lb" in outcome_lower or "leg bye" in outcome_lower:
        return 0

    if outcome_lower.endswith("b") and "lb" not in outcome_lower:
        return 0

    match = re.match(r"^(\d+)", outcome_lower)
    if match:
        return int(match.group(1))

    return 0


def parse_2023_total_runs(score):
    if pd.isna(score):
        return 0
    return int(score)


def parse_2023_extras_runs(total_runs, batsman_runs):
    return max(int(total_runs) - int(batsman_runs), 0)


def parse_2023_is_wicket(outcome, comment):
    outcome = clean_text(outcome)
    comment = clean_text(comment)

    outcome_lower = "" if outcome is None else outcome.lower()
    comment_lower = "" if comment is None else comment.lower()

    if outcome_lower == "w":
        return 1

    wicket_signals = [
        " out,",
        " c ",
        " lbw ",
        " run out",
        " st ",
        " b ",
        " hit wicket",
    ]
    if any(signal in comment_lower for signal in wicket_signals):
        return 1

    return 0


def parse_2023_dismissal_kind(outcome, comment):
    if parse_2023_is_wicket(outcome, comment) == 0:
        return None

    comment = clean_text(comment)
    comment_lower = "" if comment is None else comment.lower()

    if "run out" in comment_lower:
        return "run out"
    if "lbw" in comment_lower:
        return "lbw"
    if "st " in comment_lower:
        return "stumped"
    if "hit wicket" in comment_lower:
        return "hit wicket"
    if "caught" in comment_lower or " c " in comment_lower:
        return "caught"
    if " bowled" in comment_lower or " b " in comment_lower:
        return "bowled"

    return "wicket"


def parse_2023_player_out(comment, batter):
    if parse_2023_is_wicket(None, comment) == 0:
        return None
    return clean_player_name(batter)


def normalize_match_type_2022(match_number):
    value = clean_text(match_number)
    if value is None:
        return None

    value_lower = value.lower()
    if "final" in value_lower:
        return "Final"
    if "eliminator" in value_lower:
        return "Eliminator"
    if "qualifier" in value_lower:
        return value
    return "Group"


def load_2023_deliveries():
    df = pd.read_csv(BALL_2023_PATH)

    df["match_id"] = df["match_no"]
    df["season"] = 2023
    df["inning"] = df["inningno"]
    df["over_number"] = pd.to_numeric(df["over"], errors="coerce").fillna(0).astype(float).astype(int)
    df["ball_number"] = pd.to_numeric(df["ballnumber"], errors="coerce").fillna(0).astype(int)
    df["over_decimal"] = pd.to_numeric(df["over"], errors="coerce")
    df["batter"] = df["batter"].apply(clean_player_name)
    df["bowler"] = df["bowler"].apply(clean_player_name)
    df["comment"] = df["comment"].apply(clean_text)
    df["batsman_runs"] = df["outcome"].apply(parse_2023_batsman_runs)
    df["total_runs"] = df["score"].apply(parse_2023_total_runs)
    df["extras_runs"] = df.apply(
        lambda row: parse_2023_extras_runs(row["total_runs"], row["batsman_runs"]),
        axis=1,
    )
    df["is_wicket"] = df.apply(
        lambda row: parse_2023_is_wicket(row["outcome"], row["comment"]),
        axis=1,
    )
    df["dismissal_kind"] = df.apply(
        lambda row: parse_2023_dismissal_kind(row["outcome"], row["comment"]),
        axis=1,
    )
    df["player_out"] = df.apply(
        lambda row: parse_2023_player_out(row["comment"], row["batter"]),
        axis=1,
    )
    df["batting_team"] = None

    final_cols = [
        "match_id",
        "season",
        "inning",
        "over_number",
        "ball_number",
        "over_decimal",
        "batter",
        "bowler",
        "batsman_runs",
        "extras_runs",
        "total_runs",
        "is_wicket",
        "dismissal_kind",
        "player_out",
        "comment",
        "batting_team",
    ]
    return df[final_cols].copy()


def load_2022_deliveries():
    df = pd.read_csv(BALL_2022_PATH)

    df["match_id"] = df["ID"]
    df["season"] = 2022
    df["inning"] = df["innings"]
    df["over_number"] = pd.to_numeric(df["overs"], errors="coerce").fillna(0).astype(int)
    df["ball_number"] = pd.to_numeric(df["ballnumber"], errors="coerce").fillna(0).astype(int)
    df["over_decimal"] = df["over_number"] + (df["ball_number"] / 10.0)
    df["batter"] = df["batter"].apply(clean_player_name)
    df["bowler"] = df["bowler"].apply(clean_player_name)
    df["batsman_runs"] = pd.to_numeric(df["batsman_run"], errors="coerce").fillna(0).astype(int)
    df["extras_runs"] = pd.to_numeric(df["extras_run"], errors="coerce").fillna(0).astype(int)
    df["total_runs"] = pd.to_numeric(df["total_run"], errors="coerce").fillna(0).astype(int)
    df["is_wicket"] = pd.to_numeric(df["isWicketDelivery"], errors="coerce").fillna(0).astype(int)
    df["dismissal_kind"] = df["kind"].apply(clean_text)
    df["player_out"] = df["player_out"].apply(clean_player_name)
    df["comment"] = None
    df["batting_team"] = df["BattingTeam"].apply(clean_team_name)

    final_cols = [
        "match_id",
        "season",
        "inning",
        "over_number",
        "ball_number",
        "over_decimal",
        "batter",
        "bowler",
        "batsman_runs",
        "extras_runs",
        "total_runs",
        "is_wicket",
        "dismissal_kind",
        "player_out",
        "comment",
        "batting_team",
    ]
    return df[final_cols].copy()


def load_2023_matches():
    df = pd.read_csv(MATCH_2023_PATH)

    df["match_id"] = df["match_number"]
    df["season"] = pd.to_numeric(df["season"], errors="coerce").fillna(2023).astype(int)
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")
    df["match_number"] = df["match_number"].astype(str)
    df["match_type"] = df["match_type"].apply(clean_text)
    df["venue"] = df["venue"].apply(clean_text)
    df["city"] = df["location"].apply(clean_text)
    df["team1"] = df["team1"].apply(clean_team_name)
    df["team2"] = df["team2"].apply(clean_team_name)
    df["toss_winner"] = df["toss_won"].apply(clean_team_name)
    df["toss_decision"] = df["toss_decision"].apply(clean_text)
    df["winner"] = df["winner"].apply(clean_team_name)

    winner_runs = pd.to_numeric(df["winner_runs"], errors="coerce")
    winner_wickets = pd.to_numeric(df["winner_wickets"], errors="coerce")

    df["won_by"] = winner_runs.apply(lambda x: "runs" if pd.notna(x) and x > 0 else None)
    df.loc[winner_wickets.notna() & (winner_wickets > 0), "won_by"] = "wickets"

    df["margin"] = winner_runs
    df.loc[winner_wickets.notna() & (winner_wickets > 0), "margin"] = winner_wickets

    df["player_of_match"] = df["man_of_match"].apply(clean_player_name)

    final_cols = [
        "match_id",
        "season",
        "date",
        "match_number",
        "match_type",
        "venue",
        "city",
        "team1",
        "team2",
        "toss_winner",
        "toss_decision",
        "winner",
        "won_by",
        "margin",
        "player_of_match",
    ]
    return df[final_cols].copy()


def load_2022_matches():
    df = pd.read_csv(MATCH_2022_PATH)

    df["match_id"] = df["ID"]
    df["season"] = pd.to_numeric(df["Season"], errors="coerce").fillna(2022).astype(int)
    df["date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["match_number"] = df["MatchNumber"].astype(str)
    df["match_type"] = df["MatchNumber"].apply(normalize_match_type_2022)
    df["venue"] = df["Venue"].apply(clean_text)
    df["city"] = df["City"].apply(clean_text)
    df["team1"] = df["Team1"].apply(clean_team_name)
    df["team2"] = df["Team2"].apply(clean_team_name)
    df["toss_winner"] = df["TossWinner"].apply(clean_team_name)
    df["toss_decision"] = df["TossDecision"].apply(clean_text)
    df["winner"] = df["WinningTeam"].apply(clean_team_name)
    df["won_by"] = df["WonBy"].apply(clean_text)
    df["margin"] = pd.to_numeric(df["Margin"], errors="coerce")
    df["player_of_match"] = df["Player_of_Match"].apply(clean_player_name)

    final_cols = [
        "match_id",
        "season",
        "date",
        "match_number",
        "match_type",
        "venue",
        "city",
        "team1",
        "team2",
        "toss_winner",
        "toss_decision",
        "winner",
        "won_by",
        "margin",
        "player_of_match",
    ]
    return df[final_cols].copy()


def create_indexes(conn):
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_deliveries_season ON deliveries(season)",
        "CREATE INDEX IF NOT EXISTS idx_deliveries_batter ON deliveries(batter)",
        "CREATE INDEX IF NOT EXISTS idx_deliveries_bowler ON deliveries(bowler)",
        "CREATE INDEX IF NOT EXISTS idx_deliveries_match_id ON deliveries(match_id)",
        "CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season)",
        "CREATE INDEX IF NOT EXISTS idx_matches_winner ON matches(winner)",
        "CREATE INDEX IF NOT EXISTS idx_matches_match_type ON matches(match_type)",
    ]
    for stmt in index_statements:
        conn.execute(stmt)


def validate_input_files():
    required = [
        BALL_2023_PATH,
        MATCH_2023_PATH,
        BALL_2022_PATH,
        MATCH_2022_PATH,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required input files:\n" + "\n".join(missing)
        )


def main():
    validate_input_files()

    deliveries_2023 = load_2023_deliveries()
    deliveries_2022 = load_2022_deliveries()
    matches_2023 = load_2023_matches()
    matches_2022 = load_2022_matches()

    deliveries = pd.concat([deliveries_2022, deliveries_2023], ignore_index=True)
    matches = pd.concat([matches_2022, matches_2023], ignore_index=True)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        deliveries.to_sql("deliveries", conn, if_exists="replace", index=False)
        matches.to_sql("matches", conn, if_exists="replace", index=False)
        create_indexes(conn)

    print(f"SQLite database created at: {DB_PATH}")
    print(f"deliveries rows: {len(deliveries)}")
    print(f"matches rows: {len(matches)}")
    print("\nDeliveries columns:")
    print(deliveries.columns.tolist())
    print("\nMatches columns:")
    print(matches.columns.tolist())


if __name__ == "__main__":
    main()