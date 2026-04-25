"""
layers/normalizer.py
Cleans and classifies every question before the agent loop starts.

Key outputs
-----------
question      : entity-resolved question text
zone          : 2 = historical (IPL 2022/2023), 3 = current/live
mixed_zone    : True when the question spans BOTH zone-3 (current) AND zone-2 (historical)
                e.g. "What is Dhoni's current status and how did he bat in IPL 2023?"
intent        : primary intent (statistical | narrative | causal | comparative | current)
sub_intents   : ALL intents present — router uses this to decide how many tools are needed
entities      : resolved canonical names found in the question
sub_questions : explicit sub-questions split on " and " (used by goal decomposer)
scope_trap    : True if question is too broad to answer meaningfully
"""

import re

# ---------------------------------------------------------------------------
# Entity map
# ---------------------------------------------------------------------------

ENTITY_MAP = {
    "virat": "Virat Kohli", "kohli": "Virat Kohli",
    "king kohli": "Virat Kohli", "vk": "Virat Kohli",
    "rohit": "Rohit Sharma", "hitman": "Rohit Sharma", "ro": "Rohit Sharma",
    "dhoni": "MS Dhoni", "msd": "MS Dhoni", "thala": "MS Dhoni",
    "bumrah": "Jasprit Bumrah",
    "jadeja": "Ravindra Jadeja", "jaddu": "Ravindra Jadeja",
    "hardik": "Hardik Pandya", "pandya": "Hardik Pandya",
    "kl rahul": "KL Rahul", "rahul": "KL Rahul",
    "shami": "Mohammed Shami",
    "chahal": "Yuzvendra Chahal",
    "gill": "Shubman Gill",
    "ruturaj": "Ruturaj Gaikwad", "gaikwad": "Ruturaj Gaikwad",
    "warner": "David Warner",
    "faf": "Faf du Plessis",
    "rashid": "Rashid Khan",
    "mi": "Mumbai Indians", "mumbai": "Mumbai Indians",
    "csk": "Chennai Super Kings", "chennai": "Chennai Super Kings",
    "rcb": "Royal Challengers Bengaluru",
    "bangalore": "Royal Challengers Bengaluru",
    "bengaluru": "Royal Challengers Bengaluru",
    "kkr": "Kolkata Knight Riders", "kolkata": "Kolkata Knight Riders",
    "srh": "Sunrisers Hyderabad", "hyderabad": "Sunrisers Hyderabad",
    "dc": "Delhi Capitals", "delhi": "Delhi Capitals",
    "pbks": "Punjab Kings", "punjab": "Punjab Kings",
    "rr": "Rajasthan Royals", "rajasthan": "Rajasthan Royals",
    "gt": "Gujarat Titans", "gujarat": "Gujarat Titans",
    "lsg": "Lucknow Super Giants", "lucknow": "Lucknow Super Giants",
}

# ---------------------------------------------------------------------------
# Keyword sets
# ---------------------------------------------------------------------------

ZONE_3_SIGNALS = [
    "now", "currently", "today", "latest", "recent",
    "this season", "at the moment", "still", "right now",
    "is he", "is she", "are they", "who is the current",
    "current captain", "current coach", "retired", "playing now",
    "this year", "2025", "2026", "current status", "nowadays",
]

# Signals that force zone back to 2 even if a zone-3 word is present
ZONE_2_ANCHORS = [r"\b2022\b", r"\b2023\b"]

STATISTICAL_KW = [
    "runs", "wickets", "average", "strike rate", "economy",
    "centuries", "fifties", "catches", "score", "total", "highest",
    "lowest", "most", "least", "how many", "stats", "statistics",
    "batting average", "bowling average", "points table", "standings",
    "won", "winner", "win", "final", "champion", "matches",
    "top scorer", "leading wicket", "tally", "count",
]

CAUSAL_KW = [
    "why", "reason", "because", "cause", "what led",
    "how did it happen", "what caused",
]

COMPARATIVE_KW = [
    "compare", " vs ", " versus ", "better than",
    "difference between", "who is better", "which team is",
    "best between", "head to head",
]

NARRATIVE_KW = [
    "what did", "describe", "explain", "tell me about",
    "analyst", "commentary", "review", "report", "analysis",
    "strategy", "approach", "tactics", "said about", "thought about",
    "what happened", "how did they", "write up",
]

CURRENT_KW = [
    "current", "currently", "now", "today", "latest", "recent",
    "right now", "at the moment", "this year", "still playing",
    "retired", "status", "playing now",
]

SCOPE_TRAPS = [
    "everything about", "tell me all", "full summary of",
    "complete analysis", "all about", "everything that happened",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_zone(q_lower: str) -> int:
    """Return 3 if live/current signals present and not overridden by a year anchor."""
    has_zone3 = any(t in q_lower for t in ZONE_3_SIGNALS)
    has_year_anchor = any(re.search(p, q_lower) for p in ZONE_2_ANCHORS)
    if has_zone3 and not has_year_anchor:
        return 3
    return 2


def _detect_mixed_zone(q_lower: str, zone: int) -> bool:
    """
    True when the question contains BOTH a current/live signal AND a
    historical (2022/2023) reference or statistical keyword.
    Example: "What is Dhoni's current status and how did he bat in IPL 2023?"
    """
    if zone != 3:
        return False
    has_current = any(k in q_lower for k in CURRENT_KW)
    has_historical = (
        bool(re.search(r"\b(2022|2023)\b", q_lower))
        or any(k in q_lower for k in STATISTICAL_KW)
    )
    return has_current and has_historical


def _detect_intents(q_lower: str, zone: int) -> tuple[str, list[str]]:
    """
    Return (primary_intent, sub_intents_list).

    sub_intents captures every intent dimension present so the goal
    decomposer can create the right number of goals.
    """
    present = []

    if any(k in q_lower for k in CURRENT_KW) and zone == 3:
        present.append("current")

    if any(k in q_lower for k in STATISTICAL_KW):
        present.append("statistical")

    if any(k in q_lower for k in NARRATIVE_KW):
        present.append("narrative")

    if any(k in q_lower for k in CAUSAL_KW):
        present.append("causal")

    if any(k in q_lower for k in COMPARATIVE_KW):
        present.append("comparative")

    # Deduplicate while preserving order
    seen = set()
    sub_intents = []
    for i in present:
        if i not in seen:
            seen.add(i)
            sub_intents.append(i)

    if not sub_intents:
        sub_intents = ["narrative"]

    # Primary intent: pick the most specific one
    priority = ["causal", "comparative", "current", "statistical", "narrative"]
    primary = next((p for p in priority if p in sub_intents), sub_intents[0])

    return primary, sub_intents


def _resolve_entities(question: str) -> tuple[str, list[str]]:
    resolved = question
    for alias, canonical in sorted(ENTITY_MAP.items(), key=lambda x: -len(x[0])):
        resolved = re.sub(
            rf"\b{re.escape(alias)}\b", canonical, resolved, flags=re.IGNORECASE
        )
    entities = list(
        {e for e in ENTITY_MAP.values() if e.lower() in resolved.lower()}
    )
    return resolved, entities


def _split_sub_questions(resolved: str) -> list[str]:
    q_lower = resolved.lower()
    if " and " in q_lower:
        parts = resolved.split(" and ", 1)
        if all(len(p.strip()) > 15 for p in parts):
            return [p.strip() for p in parts]
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_query(question: str) -> dict:
    q_lower = question.lower()

    zone = _detect_zone(q_lower)
    mixed_zone = _detect_mixed_zone(q_lower, zone)
    resolved, entities = _resolve_entities(question)
    intent, sub_intents = _detect_intents(q_lower, zone)
    sub_questions = _split_sub_questions(resolved)

    # Scope trap
    scope_trap = None
    scope_response = None
    for trap in SCOPE_TRAPS:
        if trap in q_lower:
            scope_trap = trap
            scope_response = (
                "That's very broad. I can focus on one of these areas:\n"
                "• Batting performance\n• Bowling performance\n"
                "• Match results\n• Team analysis\n• Player profiles\n\n"
                "Which aspect of IPL 2022 or 2023 would you like to explore?"
            )
            break

    return {
        "question":           resolved,
        "original":           question,
        "zone":               zone,
        "mixed_zone":         mixed_zone,
        "intent":             intent,
        "sub_intents":        sub_intents,
        "entities":           entities,
        "sub_questions":      sub_questions,
        "scope_trap":         scope_trap,
        "scope_trap_response": scope_response,
    }