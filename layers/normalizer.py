"""
layers/normalizer.py

Cleans and classifies every question before the agent loop starts.
- Resolves entity aliases to canonical names
- Detects temporal zone (1=historical, 2=corpus, 3=live/current)
- Classifies intent (statistical, narrative, causal, comparative, current)
- Splits compound questions into sub-questions
- Detects scope traps ("everything about IPL 2023")
"""

import re

# ── Entity resolution map ─────────────────────────────────────────────────────
ENTITY_MAP = {
    # Players
    "virat": "Virat Kohli", "kohli": "Virat Kohli", "king kohli": "Virat Kohli",
    "vk": "Virat Kohli",
    "rohit": "Rohit Sharma", "hitman": "Rohit Sharma", "ro": "Rohit Sharma",
    "dhoni": "MS Dhoni", "msd": "MS Dhoni", "thala": "MS Dhoni",
    "bumrah": "Jasprit Bumrah", "boom boom": "Jasprit Bumrah",
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
    # Teams
    "mi": "Mumbai Indians", "mumbai": "Mumbai Indians",
    "csk": "Chennai Super Kings", "chennai": "Chennai Super Kings",
    "rcb": "Royal Challengers Bengaluru", "bangalore": "Royal Challengers Bengaluru",
    "bengaluru": "Royal Challengers Bengaluru",
    "kkr": "Kolkata Knight Riders", "kolkata": "Kolkata Knight Riders",
    "srh": "Sunrisers Hyderabad", "hyderabad": "Sunrisers Hyderabad",
    "dc": "Delhi Capitals", "delhi": "Delhi Capitals",
    "pbks": "Punjab Kings", "punjab": "Punjab Kings",
    "rr": "Rajasthan Royals", "rajasthan": "Rajasthan Royals",
    "gt": "Gujarat Titans", "gujarat": "Gujarat Titans",
    "lsg": "Lucknow Super Giants", "lucknow": "Lucknow Super Giants",
}

# ── Zone detection keywords ───────────────────────────────────────────────────
ZONE_3_TRIGGERS = [
    "now", "currently", "today", "latest", "recent",
    "this season", "at the moment", "still", "right now",
    "is he", "is she", "are they", "who is the current",
    "current captain", "current coach", "retired", "playing now",
    "this year", "2025", "2026"
]

# ── Intent keywords ───────────────────────────────────────────────────────────
STATISTICAL_KW = [
    "runs", "wickets", "average", "strike rate", "economy",
    "centuries", "fifties", "catches", "score", "total", "highest",
    "lowest", "most", "least", "how many", "stats", "statistics",
    "batting average", "bowling average", "points table", "standings"
]
CAUSAL_KW = ["why", "reason", "because", "cause", "what led", "how did it happen"]
COMPARATIVE_KW = ["compare", "vs", "versus", "better than", "difference between",
                  "who is better", "which team", "best between"]
NARRATIVE_KW = [
    "what did", "describe", "explain", "tell me about",
    "analyst", "commentary", "review", "report", "analysis",
    "how did", "what was the performance"
]
SCOPE_TRAPS = [
    "everything about", "tell me all", "full summary of",
    "complete analysis", "all about", "everything that happened"
]


def normalize_query(question: str) -> dict:
    """
    Returns normalized question dict with zone, intent, entities, sub-questions.
    """
    q_lower = question.lower()

    # ── Zone detection ────────────────────────────────────────────────────
    zone = 2  # default: corpus-present
    for trigger in ZONE_3_TRIGGERS:
        if trigger in q_lower:
            zone = 3
            break

    # Explicit corpus year mentioned → at most zone 2
    if re.search(r'\b(2022|2023)\b', q_lower):
        zone = min(zone, 2)

    # ── Entity resolution ─────────────────────────────────────────────────
    resolved = question
    for alias, canonical in sorted(ENTITY_MAP.items(), key=lambda x: -len(x[0])):
        resolved = re.sub(
            rf'\b{re.escape(alias)}\b', canonical,
            resolved, flags=re.IGNORECASE
        )

    # ── Entity extraction (from resolved question) ────────────────────────
    all_canonical = set(ENTITY_MAP.values())
    entities = [e for e in all_canonical if e.lower() in resolved.lower()]
    entities = list(set(entities))

    # ── Scope trap detection ──────────────────────────────────────────────
    scope_trap = None
    scope_response = None
    for trap in SCOPE_TRAPS:
        if trap in q_lower:
            scope_trap = trap
            scope_response = (
                "That's a very broad question. I can focus on one of these areas:\n"
                "• Batting performance\n• Bowling performance\n"
                "• Match results\n• Team analysis\n• Player profiles\n\n"
                "Which aspect of IPL 2022 or 2023 would you like to explore?"
            )
            break

    # ── Intent classification ─────────────────────────────────────────────
    # Order matters — check more specific first
    intent = "narrative"  # default
    if any(k in q_lower for k in STATISTICAL_KW):
        intent = "statistical"
    if any(k in q_lower for k in CAUSAL_KW):
        intent = "causal"
    if any(k in q_lower for k in COMPARATIVE_KW):
        intent = "comparative"
    if zone == 3:
        intent = "current"

    # ── Compound question splitting ───────────────────────────────────────
    # Split on " and " only if both parts are substantial
    sub_questions = []
    if " and " in q_lower:
        parts = resolved.split(" and ", 1)
        if len(parts) == 2:
            p1, p2 = parts[0].strip(), parts[1].strip()
            if len(p1) > 15 and len(p2) > 10:
                sub_questions = [p1, p2]

    return {
        "question": resolved,
        "original": question,
        "zone": zone,
        "intent": intent,
        "entities": entities,
        "sub_questions": sub_questions,
        "scope_trap": scope_trap,
        "scope_trap_response": scope_response
    }