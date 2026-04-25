"""
layers/gatekeeper.py
First decision point. Runs before any tool or API call.

Decision order (all keyword-based — no LLM call, zero latency, zero token cost):
  1. Trivial / meta patterns    → direct_answer
  2. Investment / betting       → refuse
  3. Hard year-scope check      → refuse  (non-2022/2023 years)
  4. Domain relevance check     → refuse  (not cricket-related at all)

Why no LLM here:
  - Gatekeeper fires on every question including cached ones.
  - An LLM call here adds latency, burns tokens, and hits rate limits.
  - The keyword lists below are comprehensive enough for the IPL domain.
  - If the gatekeeper passes something it shouldn't, the normalizer and
    router will fail to find evidence → insufficient_evidence refusal anyway.
"""

import ast
import operator
import re


# ---------------------------------------------------------------------------
# Corpus scope
# ---------------------------------------------------------------------------

CORPUS_SEASONS = {"2022", "2023"}


# ---------------------------------------------------------------------------
# Safe arithmetic evaluator (no eval())
# ---------------------------------------------------------------------------

_OPS = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
}


def _safe_eval(expr: str):
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
        raise ValueError("Unsupported")
    result = _eval(ast.parse(expr, mode="eval").body)
    return int(result) if result == int(result) else result


# ---------------------------------------------------------------------------
# Trivial / meta patterns — answered instantly, no retrieval needed
# ---------------------------------------------------------------------------

TRIVIAL_PATTERNS = [
    (
        r"what is \d+\s*[\+\-\*\/]\s*\d+",
        lambda m: str(_safe_eval(m.group().replace("what is", "").strip())),
    ),
    (
        r"what does ipl stand for",
        lambda m: "IPL stands for Indian Premier League.",
    ),
    (
        r"^(hi|hello|hey|howdy)[\s!]*$",
        lambda m: "Hello! Ask me anything about IPL 2022 or 2023.",
    ),
    (
        r"how are you",
        lambda m: "I'm ready to answer your IPL questions!",
    ),
    (
        r"what can you do",
        lambda m: (
            "I can answer questions about IPL 2022 and 2023 — "
            "statistics, match results, player performance, and analyst commentary."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Investment / betting triggers — refuse immediately
# ---------------------------------------------------------------------------

REFUSE_TRIGGERS = [
    "bet", "betting", "gamble", "gambling",
    "invest", "investment", "buy shares", "sell shares",
    "fantasy team", "which team to pick", "should i pick",
    "predict the winner", "who will win",
    "should i buy", "should i sell",
]


# ---------------------------------------------------------------------------
# Cricket domain vocabulary — if NONE of these appear, refuse as off-topic
# ---------------------------------------------------------------------------

CRICKET_DOMAIN_TERMS = [
    # League / tournament
    "ipl", "indian premier league", "cricket", "t20",
    "match", "season", "league", "tournament",
    "final", "qualifier", "eliminator", "playoff",
    "points table", "standings", "scorecard",
    # Actions / events
    "runs", "run", "wicket", "wickets",
    "batting", "bowling", "bowler", "batter", "batsman",
    "all rounder", "all-rounder", "fielding", "fielder",
    "catch", "stumping", "run out", "duck",
    "century", "fifty", "half century",
    "six", "four", "boundary",
    "over", "powerplay", "death overs", "middle overs",
    "innings", "chase", "target", "toss",
    # Stats
    "strike rate", "average", "economy", "economy rate",
    "net run rate", "nrr", "batting average", "bowling average",
    "best figures", "purple cap", "orange cap",
    "most runs", "most wickets",
    # Team roles / squad
    "captain", "captaincy", "coach", "squad", "playing xi",
    "auction", "retained", "released", "injury",
    "impact player", "substitute",
    # Teams
    "csk", "chennai super kings",
    "mi", "mumbai indians",
    "rcb", "royal challengers",
    "gt", "gujarat titans",
    "rr", "rajasthan royals",
    "lsg", "lucknow super giants",
    "dc", "delhi capitals",
    "kkr", "kolkata knight riders",
    "pbks", "punjab kings",
    "srh", "sunrisers hyderabad",
]

CRICKET_PLAYER_TERMS = [
    "kohli", "virat",
    "dhoni", "msd", "thala", "mahi",
    "rohit", "hitman",
    "bumrah", "jasprit",
    "shami", "mohammed shami",
    "rashid", "rashid khan",
    "gill", "shubman",
    "buttler", "jos",
    "rahul", "kl rahul",
    "jadeja", "jaddu",
    "ruturaj", "gaikwad",
    "faf", "du plessis",
    "maxwell",
    "suryakumar", "sky",
    "hardik", "pandya",
    "pant", "rishabh",
    "samson", "sanju",
    "chahal", "yuzvendra",
    "siraj",
    "natarajan",
    "warner", "david warner",
    "narine", "sunil",
    "russell", "andre",
    "pollard", "kieron",
    "boult", "trent",
    "ashwin",
    "umran",
    "arshdeep",
    "kishan", "ishan",
    "tilak",
    "tendulkar", "sachin",
    "gayle", "chris gayle",
    "de villiers", "abd",
    "raina", "suresh",
]


def _is_cricket_related(q: str) -> bool:
    """Return True if the question contains at least one cricket/IPL term."""
    return (
        any(term in q for term in CRICKET_DOMAIN_TERMS)
        or any(player in q for player in CRICKET_PLAYER_TERMS)
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def gatekeeper_check(question: str) -> dict:
    q = question.lower().strip()

    # 1. Trivial / meta
    for pattern, handler in TRIVIAL_PATTERNS:
        m = re.search(pattern, q)
        if m:
            return {"action": "direct_answer", "answer": handler(m)}

    # 2. Investment / betting — check BEFORE year check so
    #    "bet on IPL 2024" is refused for the right reason, not scope reason
    for trigger in REFUSE_TRIGGERS:
        if trigger in q:
            return {
                "action": "refuse",
                "answer": (
                    "This system provides factual IPL cricket information only. "
                    "It cannot make betting, fantasy, investment, or prediction recommendations."
                ),
            }

    # 3. Hard year-scope check
    years = re.findall(r"\b(20\d{2})\b", q)
    for year in years:
        if year not in CORPUS_SEASONS:
            return {
                "action": "refuse",
                "answer": (
                    f"This system only covers IPL {' and '.join(sorted(CORPUS_SEASONS))}. "
                    f"Data for IPL {year} is not available in this corpus."
                ),
            }

    # 4. Domain relevance — refuse if zero cricket signals found
    if not _is_cricket_related(q):
        return {
            "action": "refuse",
            "answer": (
                "This system only answers IPL/cricket-related questions "
                "for the 2022 and 2023 seasons."
            ),
        }

    return {"action": "proceed"}