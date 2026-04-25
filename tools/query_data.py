import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "ipl.db"

TEAM_ALIASES = {
    "csk": "Chennai Super Kings",
    "chennai": "Chennai Super Kings",
    "mi": "Mumbai Indians",
    "mumbai": "Mumbai Indians",
    "rcb": "Royal Challengers Bengaluru",
    "royal challengers bangalore": "Royal Challengers Bengaluru",
    "royal challengers bengaluru": "Royal Challengers Bengaluru",
    "bangalore": "Royal Challengers Bengaluru",
    "bengaluru": "Royal Challengers Bengaluru",
    "gt": "Gujarat Titans",
    "gujarat": "Gujarat Titans",
    "rr": "Rajasthan Royals",
    "rajasthan": "Rajasthan Royals",
    "srh": "Sunrisers Hyderabad",
    "hyderabad": "Sunrisers Hyderabad",
    "dc": "Delhi Capitals",
    "delhi": "Delhi Capitals",
    "pbks": "Punjab Kings",
    "punjab": "Punjab Kings",
    "kkr": "Kolkata Knight Riders",
    "kolkata": "Kolkata Knight Riders",
    "lsg": "Lucknow Super Giants",
    "lucknow": "Lucknow Super Giants",
}

PLAYER_ALIASES = {
    "kohli": "Virat Kohli",
    "virat": "Virat Kohli",
    "gill": "Shubman Gill",
    "shubman": "Shubman Gill",
    "dhoni": "MS Dhoni",
    "ms dhoni": "MS Dhoni",
    "rohit": "Rohit Sharma",
    "bumrah": "Jasprit Bumrah",
    "shami": "Mohammed Shami",
    "surya": "Suryakumar Yadav",
    "sky": "Suryakumar Yadav",
    "faf": "Faf du Plessis",
    "jadeja": "Ravindra Jadeja",
    "hardik": "Hardik Pandya",
    "rashid": "Rashid Khan",
    "warner": "David Warner",
    "rahul": "KL Rahul",
    "kl rahul": "KL Rahul",
    "buttler": "Jos Buttler",
    "jaiswal": "Yashasvi Jaiswal",
    "maxwell": "Glenn Maxwell",
    "siraj": "Mohammed Siraj",
}

WICKET_EXCLUDE_KINDS = (
    "run out",
    "retired hurt",
    "retired out",
    "obstructing the field",
)


def get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def extract_year(question: str) -> Optional[int]:
    match = re.search(r"\b(20\d{2})\b", question)
    return int(match.group(1)) if match else None


def resolve_team(question: str) -> Optional[str]:
    q = normalize_text(question)
    for alias, full_name in TEAM_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", q):
            return full_name
    return None


def resolve_player(question: str) -> Optional[str]:
    q = normalize_text(question)
    for alias, full_name in PLAYER_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", q):
            return full_name
    return None


def resolve_players_for_compare(question: str) -> List[str]:
    q = normalize_text(question)
    players: List[str] = []
    for alias, full_name in PLAYER_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", q) and full_name not in players:
            players.append(full_name)
    return players[:2]


def run_select(sql: str, params: Tuple = ()) -> Dict[str, Any]:
    if not sql.strip().lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    return {
        "success": True,
        "sql": sql.strip(),
        "params": list(params),
        "columns": list(rows[0].keys()) if rows else [],
        "rows": [dict(row) for row in rows],
        "row_count": len(rows),
    }


def classify_question(question: str) -> str:
    q = normalize_text(question)

    if "compare" in q:
        return "compare_players_batting"

    if "most runs" in q or "top scorer" in q or "highest run scorer" in q or "leading run scorer" in q:
        return "top_run_scorer"

    if "most wickets" in q or "top wicket" in q or "leading wicket" in q:
        return "top_wicket_taker"

    if ("winner" in q or "won" in q or "which team" in q) and ("ipl" in q or "season" in q):
        return "season_winner"

    if ("highest score" in q or "highest individual score" in q):
        return "highest_individual_score"

    if "how many matches" in q and "win" in q:
        return "team_wins"

    if "strike rate" in q:
        return "strike_rate"

    if "economy" in q:
        return "economy"

    if "player of the match" in q or "man of the match" in q:
        return "player_of_match"

    if "final" in q and "winner" in q:
        return "final_winner"
    
    if "wicket" in q and resolve_player(question):
        return "player_wickets"

    if "century" in q and resolve_player(question):
        return "player_centuries"

    if "best player" in q or "player of the tournament" in q or "most valuable player" in q:
        return "player_of_tournament"

    return "unknown"


def build_sql(question: str) -> Tuple[Optional[str], Optional[Tuple], Optional[str]]:
    qtype = classify_question(question)
    year = extract_year(question)
    team = resolve_team(question)
    player = resolve_player(question)
    players = resolve_players_for_compare(question)

    if qtype == "top_run_scorer" and year:
        sql = """
        SELECT batter AS player, SUM(batsman_runs) AS total_runs
        FROM deliveries
        WHERE season = ?
        GROUP BY batter
        ORDER BY total_runs DESC
        LIMIT 5
        """
        return sql, (year,), "deliveries"
    

    if qtype == "player_wickets" and year and player:
        placeholders = ",".join(["?"] * len(WICKET_EXCLUDE_KINDS))
        sql = f"""
    SELECT bowler AS player, COUNT(*) AS wickets
    FROM deliveries
    WHERE season = ?
      AND bowler = ?
      AND is_wicket = 1
      AND (dismissal_kind IS NULL OR LOWER(dismissal_kind) NOT IN ({placeholders}))
    GROUP BY bowler
    """
    return sql, (year, player, *WICKET_EXCLUDE_KINDS), "deliveries"
    if qtype == "top_wicket_taker" and year:
        placeholders = ",".join(["?"] * len(WICKET_EXCLUDE_KINDS))
        sql = f"""
        SELECT bowler AS player, COUNT(*) AS wickets
        FROM deliveries
        WHERE season = ?
          AND is_wicket = 1
          AND (dismissal_kind IS NULL OR LOWER(dismissal_kind) NOT IN ({placeholders}))
        GROUP BY bowler
        ORDER BY wickets DESC
        LIMIT 5
        """
        return sql, (year, *WICKET_EXCLUDE_KINDS), "deliveries"

    if qtype in ("season_winner", "final_winner") and year:
        sql = """
        SELECT season, winner, match_number, match_type, venue, date
        FROM matches
        WHERE season = ?
          AND LOWER(COALESCE(match_type, '')) LIKE '%final%'
        LIMIT 1
        """
        return sql, (year,), "matches"

    if qtype == "highest_individual_score" and year:
        sql = """
        SELECT batter AS player, MAX(runs_scored) AS highest_score
        FROM (
            SELECT season, match_id, batter, SUM(batsman_runs) AS runs_scored
            FROM deliveries
            WHERE season = ?
            GROUP BY season, match_id, batter
        ) t
        GROUP BY batter
        ORDER BY highest_score DESC
        LIMIT 5
        """
        return sql, (year,), "deliveries"

    if qtype == "team_wins" and year and team:
        sql = """
        SELECT winner AS team, COUNT(*) AS wins
        FROM matches
        WHERE season = ?
          AND winner = ?
        GROUP BY winner
        """
        return sql, (year, team), "matches"

    if qtype == "strike_rate" and year and player:
        sql = """
        SELECT
            batter AS player,
            SUM(batsman_runs) AS runs,
            COUNT(*) AS balls,
            ROUND((SUM(batsman_runs) * 100.0) / COUNT(*), 2) AS strike_rate
        FROM deliveries
        WHERE season = ?
          AND batter = ?
        GROUP BY batter
        """
        return sql, (year, player), "deliveries"

    if qtype == "economy" and year and player:
        sql = """
        SELECT
            bowler AS player,
            ROUND((SUM(total_runs) * 1.0) / (COUNT(*) / 6.0), 2) AS economy,
            COUNT(*) AS balls_bowled,
            SUM(total_runs) AS runs_conceded
        FROM deliveries
        WHERE season = ?
          AND bowler = ?
        GROUP BY bowler
        """
        return sql, (year, player), "deliveries"

    if qtype == "player_of_match" and year:
        sql = """
        SELECT date, team1, team2, player_of_match
        FROM matches
        WHERE season = ?
          AND LOWER(COALESCE(match_type, '')) LIKE '%final%'
        LIMIT 1
        """
        return sql, (year,), "matches"

    if qtype == "compare_players_batting" and year and len(players) == 2:
        sql = """
        SELECT
            batter AS player,
            SUM(batsman_runs) AS runs,
            COUNT(*) AS balls,
            ROUND((SUM(batsman_runs) * 100.0) / COUNT(*), 2) AS strike_rate
        FROM deliveries
        WHERE season = ?
          AND batter IN (?, ?)
        GROUP BY batter
        ORDER BY runs DESC
        """
        return sql, (year, players[0], players[1]), "deliveries"

    return None, None, None


def query_data(question: str, table_hint: Optional[str] = None) -> Dict[str, Any]:
    sql, params, source_table = build_sql(question)

    if sql is None:
        return {
            "success": False,
            "tool": "query_data",
            "question": question,
            "error": "Unsupported question for current rule set. Add a new template for this query type.",
        }

    result = run_select(sql, params)
    result["tool"] = "query_data"
    result["question"] = question
    result["source_table"] = source_table
    return result


if __name__ == "__main__":
    test_questions = [
    "Who scored the second most runs in IPL 2023?",                  # aggregation variation
    "How many runs did Kohli score in IPL 2023?",                    # player-specific
    "Compare Kohli and Gill in IPL 2023",                            # comparison
    "How many matches did Mumbai Indians win in IPL 2022?",          # team query
    "Who scored the most runs in IPL 2025?",                         # out-of-range / no data
    "What was Bumrah's economy in IPL 2023?",                        # edge (missing player data)
    "Who is the best player in IPL 2023?",                           # ambiguous
    "Who scored the most runs in IPL 2023 and what was his strike rate?",  # multi-intent
    "Which team had the biggest margin victory in IPL 2023?",        # derived logic
    "give data"                                                      # invalid input
]

    for q in test_questions:
        print("\n" + "=" * 100)
        print("Q:", q)
        print(json.dumps(query_data(q), indent=2, default=str))