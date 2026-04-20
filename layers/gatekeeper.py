"""
layers/gatekeeper.py

First decision point. Runs before any tool or API call.
Three exits: direct_answer, refuse, or proceed.
Catches trivial questions, dangerous questions, and out-of-scope years.
"""

import re

# Questions that must be refused — no tools called ever
REFUSE_TRIGGERS = [
    "bet", "betting", "gamble", "gambling",
    "invest", "investment", "buy shares", "sell shares",
    "fantasy team", "which team to pick", "should i pick",
    "predict the winner", "who will win"
]

# Questions answerable directly without any tool
TRIVIAL_PATTERNS = [
    (r"what is \d+\s*[\+\-\*\/]\s*\d+", lambda m: str(eval(m.group().replace("what is", "").strip()))),
    (r"what does ipl stand for", lambda m: "IPL stands for Indian Premier League."),
    (r"^(hi|hello|hey|howdy)[\s!]*$", lambda m: "Hello! Ask me anything about IPL 2022 or 2023."),
    (r"how are you", lambda m: "I'm ready to answer your IPL questions!"),
    (r"what can you do", lambda m: "I can answer questions about IPL 2022 and 2023 — statistics, match results, player performance, and analyst commentary."),
]

# Only these seasons are in the corpus
CORPUS_SEASONS = {"2022", "2023"}


def gatekeeper_check(question: str) -> dict:
    """
    Returns dict with 'action' key:
      - 'direct_answer': { action, answer }
      - 'refuse':        { action, answer }
      - 'proceed':       { action }
    """
    q_lower = question.lower().strip()

    # ── Trivial direct answers ────────────────────────────────────────────
    for pattern, handler in TRIVIAL_PATTERNS:
        m = re.search(pattern, q_lower)
        if m:
            return {
                "action": "direct_answer",
                "answer": handler(m)
            }

    # ── Hard refusals ─────────────────────────────────────────────────────
    for trigger in REFUSE_TRIGGERS:
        if trigger in q_lower:
            return {
                "action": "refuse",
                "answer": (
                    "This system provides factual IPL cricket information only. "
                    "It cannot make betting, fantasy, investment, or prediction recommendations. "
                    "Please ask about match statistics, player performance, or team results."
                )
            }

    # ── Out-of-scope year detection ───────────────────────────────────────
    years_mentioned = re.findall(r'\b(20\d{2})\b', q_lower)
    for year in years_mentioned:
        if year not in CORPUS_SEASONS:
            return {
                "action": "refuse",
                "answer": (
                    f"This system only covers IPL {' and '.join(sorted(CORPUS_SEASONS))}. "
                    f"Data for IPL {year} is not available in this corpus. "
                    f"For current season information, try asking about recent news."
                )
            }

    return {"action": "proceed"}