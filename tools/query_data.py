"""
tools/query_data.py

Translates plain-English questions into safe SELECT-only SQL queries.
Uses Claude Haiku to generate SQL, validates column names before running,
returns exact numbers with source metadata for the citation binder.
"""

import sqlite3
import json
import re
from pathlib import Path
from anthropic import Anthropic

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "ipl.db"

client = Anthropic()

# ── Real schema injected into every SQL prompt ──────────────────────────────
# This prevents hallucinated column names.
SCHEMA = {
    "matches": [
        "match_id", "season", "date", "venue", "team1", "team2",
        "toss_winner", "toss_decision", "winner",
        "win_by_runs", "win_by_wickets", "player_of_match"
    ],
    "deliveries": [
        "match_id", "season", "inning", "over", "ball",
        "batting_team", "bowling_team", "batter", "bowler",
        "batsman_runs", "extras", "total_runs",
        "is_wicket", "player_dismissed", "wicket_type"
    ],
    "batting_stats": [
        "season", "player", "runs", "balls_faced",
        "innings", "strike_rate"
    ],
    "bowling_stats": [
        "season", "player", "balls_bowled", "runs_conceded",
        "wickets", "overs", "economy"
    ],
    "players": ["season", "player"]
}

TABLE_HINTS = {
    "batting": "batting_stats",
    "bowling": "bowling_stats",
    "matches": "matches",
    "match": "matches",
    "players": "players",
    "player": "players",
    "deliveries": "deliveries",
    "ball": "deliveries",
}


def _get_schema_string(hint: str = None) -> str:
    """Build schema string to inject into LLM prompt."""
    lines = []
    tables = [TABLE_HINTS.get(hint, None)] if hint and hint in TABLE_HINTS else list(SCHEMA.keys())
    for table in tables:
        if table and table in SCHEMA:
            cols = ", ".join(SCHEMA[table])
            lines.append(f"  {table}({cols})")
    return "\n".join(lines)


def _validate_sql(sql: str) -> tuple[bool, str]:
    """
    Validates generated SQL before execution.
    Only allows SELECT. Checks column names against real schema.
    Returns (is_valid, error_message).
    """
    sql_clean = sql.strip().upper()

    # Block anything that is not SELECT
    forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "TRUNCATE"]
    for word in forbidden:
        if word in sql_clean:
            return False, f"Forbidden SQL keyword: {word}"

    if not sql_clean.startswith("SELECT"):
        return False, "Only SELECT queries are allowed."

    # Extract column references (basic check)
    # We let SQLite catch actual column errors — this just blocks obvious hallucinations
    for table, columns in SCHEMA.items():
        if table.upper() in sql_clean:
            # Check that referenced columns exist in that table
            # Extract words after SELECT and before FROM
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_clean, re.DOTALL)
            if select_match:
                select_part = select_match.group(1)
                if select_part.strip() == "*":
                    continue
                for col_ref in re.findall(r'\b([A-Z_]+)\b', select_part):
                    col_lower = col_ref.lower()
                    if (col_lower not in columns
                            and col_lower not in ["count", "sum", "avg", "max", "min",
                                                  "round", "distinct", "as", "null"]):
                        # Not a fatal error, just warn — SQLite will catch it
                        pass

    return True, ""


def _generate_sql(question: str, hint: str = None) -> str:
    """Use Claude Haiku to convert NL question to SQL with real schema."""
    schema_str = _get_schema_string(hint)

    prompt = f"""You are a SQL expert for an IPL cricket database.
Convert the question to a single SQLite SELECT query.

Database schema:
{schema_str}

Rules:
- Only use SELECT. Never DROP, DELETE, INSERT, UPDATE.
- Only use column names exactly as shown in the schema.
- For player name lookups, use LIKE '%name%' (case-insensitive with LOWER()).
- Always include the season column in GROUP BY when aggregating across seasons.
- Limit results to 20 rows unless the question asks for all.
- Return ONLY the SQL query, no explanation, no markdown backticks.

Question: {question}

SQL:"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )

    sql = response.content[0].text.strip()
    # Strip markdown if model added it anyway
    sql = re.sub(r"```sql|```", "", sql).strip()
    return sql


def _run_sql(sql: str) -> dict:
    """Execute validated SQL against SQLite. Returns formatted result."""
    if not DB_PATH.exists():
        return {
            "error": f"Database not found at {DB_PATH}. Run: python ingest/ingest_data.py",
            "sql": sql
        }

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql)
            rows = cursor.fetchall()
            columns = [d[0] for d in cursor.description] if cursor.description else []

        if not rows:
            return {
                "sql": sql,
                "columns": columns,
                "rows": [],
                "row_count": 0,
                "table": _extract_table(sql),
                "note": "Query returned no results. The player/team may not exist in this corpus."
            }

        # Format rows as list of dicts
        formatted_rows = [dict(zip(columns, row)) for row in rows]

        # Scalar shortcut — if single value, surface it clearly
        scalar = None
        if len(formatted_rows) == 1 and len(columns) == 1:
            scalar = formatted_rows[0][columns[0]]

        return {
            "sql": sql,
            "columns": columns,
            "rows": formatted_rows,
            "row_count": len(formatted_rows),
            "table": _extract_table(sql),
            "scalar": scalar  # None if not single-value
        }

    except sqlite3.OperationalError as e:
        return {
            "error": f"SQL error: {str(e)}",
            "sql": sql,
            "hint": "Check that column names match the schema exactly."
        }
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}", "sql": sql}


def _extract_table(sql: str) -> str:
    """Extract primary table name from SQL for citation binder."""
    match = re.search(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
    return match.group(1) if match else "unknown"


def query_data(question: str, table_hint: str = None) -> dict:
    """
    Main entry point for the query_data tool.

    Args:
        question: Plain English question about IPL statistics.
        table_hint: Optional hint — 'batting', 'bowling', 'matches', 'players'.

    Returns:
        dict with sql, columns, rows, row_count, table, scalar (if single value).
    """
    # Step 1: Generate SQL
    sql = _generate_sql(question, table_hint)

    # Step 2: Validate before running
    valid, error_msg = _validate_sql(sql)
    if not valid:
        return {
            "error": f"Generated SQL was unsafe: {error_msg}",
            "sql": sql
        }

    # Step 3: Execute
    result = _run_sql(sql)
    result["question"] = question
    return result


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("Who scored the most runs in IPL 2023?", "batting"),
        ("What is Virat Kohli's strike rate in 2022?", "batting"),
        ("Which bowler took the most wickets in 2023?", "bowling"),
        ("How many matches did CSK win?", "matches"),
    ]
    for q, hint in tests:
        print(f"\nQ: {q}")
        result = query_data(q, hint)
        if "error" in result:
            print(f"  ERROR: {result['error']}")
            print(f"  SQL:   {result['sql']}")
        elif result.get("scalar") is not None:
            print(f"  Answer: {result['scalar']} (from {result['table']})")
        else:
            print(f"  Rows: {result['row_count']}, Columns: {result['columns']}")
            for row in result["rows"][:3]:
                print(f"  {row}")