"""
layers/goal_decomposer.py

Breaks a normalized question into trackable sub-goals.
Each goal maps to exactly one tool_type (statistical | narrative | current).
The router uses the open goal list — not hardcoded logic — to decide which
tool to call next.

Key fix: compound questions now produce MULTIPLE goals so the router
never stops after the first tool succeeds when a second tool is still needed.

Examples
--------
"Kohli's strike rate AND what analysts said about his form"
  → [goal(statistical), goal(narrative)]          ← two tools needed

"Dhoni's current status AND how he batted in IPL 2023"
  → [goal(current), goal(statistical)]            ← two tools needed

"Why did CSK struggle?"
  → [goal(narrative), goal(statistical)]          ← causal needs both

"Who scored most runs in IPL 2023?"
  → [goal(statistical)]                           ← single tool
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Keyword sets (mirror normalizer — kept local to avoid circular imports)
# ---------------------------------------------------------------------------

_STAT_KW = [
    "runs", "wickets", "average", "strike rate", "economy", "centuries",
    "fifties", "catches", "score", "total", "highest", "lowest", "most",
    "least", "how many", "stats", "statistics", "batting average",
    "bowling average", "points table", "standings", "won", "winner",
    "win", "final", "champion", "matches", "top scorer", "leading wicket",
]

_NARRATIVE_KW = [
    "analyst", "commentary", "review", "report", "analysis", "strategy",
    "tactics", "approach", "said about", "describe", "explain", "what did",
    "tell me about", "thought about", "what happened", "how did they",
]

_CAUSAL_KW = [
    "why", "reason", "because", "cause", "what led", "how did it happen",
    "what caused",
]

_COMPARATIVE_KW = [
    "compare", " vs ", " versus ", "better than", "difference between",
    "who is better", "which team is", "best between", "head to head",
]

_CURRENT_KW = [
    "current", "currently", "now", "today", "latest", "recent",
    "right now", "at the moment", "this year", "still playing",
    "retired", "status", "playing now",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_tool_type(text: str) -> str:
    t = text.lower()
    if any(k in t for k in _CURRENT_KW):
        return "current"
    if any(k in t for k in _STAT_KW):
        return "statistical"
    if any(k in t for k in _NARRATIVE_KW):
        return "narrative"
    if any(k in t for k in _CAUSAL_KW):
        return "narrative"
    return "narrative"


def _goal(description: str, tool_type: str, entity, zone: int) -> dict:
    return {
        "description":  description,
        "tool_type":    tool_type,
        "entity":       entity,
        "zone":         zone,
        "status":       "OPEN",
        "evidence_key": None,
    }


def _has_content(result: dict) -> bool:
    if not result or "error" in result:
        return False
    if "chunks"  in result: return len(result["chunks"])  > 0
    if "rows"    in result: return result.get("row_count", 0) > 0
    if "results" in result: return len(result["results"]) > 0
    return bool(result)


def _tool_type_used(tool_name: str) -> str:
    return {"search_docs": "narrative", "query_data": "statistical",
            "web_search": "current"}.get(tool_name, "narrative")


# ---------------------------------------------------------------------------
# Core decomposition
# ---------------------------------------------------------------------------

def decompose_goals(normalized: dict) -> list[dict]:
    """
    Produce the minimal ordered list of sub-goals needed to fully answer
    the question. Each goal has a distinct tool_type so the router knows
    what to call and can check sufficiency per-goal.
    """
    intent      = normalized["intent"]
    sub_intents = normalized.get("sub_intents", [intent])
    entities    = normalized["entities"]
    zone        = normalized["zone"]
    mixed_zone  = normalized.get("mixed_zone", False)
    sub_qs      = normalized.get("sub_questions", [])
    question    = normalized["question"]
    q_lower     = question.lower()

    entity = entities[0] if entities else None
    goals: list[dict] = []

    # ------------------------------------------------------------------
    # 1. Mixed-zone: question spans current AND historical
    #    e.g. "Dhoni's current status and how he batted in 2023"
    # ------------------------------------------------------------------
    if mixed_zone:
        goals.append(_goal(
            f"Retrieve current/live information about {entity or 'the subject'}",
            "current", entity, 3,
        ))
        goals.append(_goal(
            f"Retrieve historical IPL statistics for {entity or 'the subject'}",
            "statistical", entity, 2,
        ))
        return goals

    # ------------------------------------------------------------------
    # 2. Explicit sub-questions split on "and"
    #    e.g. "What was Kohli's strike rate AND what did analysts say?"
    # ------------------------------------------------------------------
    if sub_qs and len(sub_qs) == 2:
        seen_types: set[str] = set()
        for sq in sub_qs:
            tt = _infer_tool_type(sq)
            if tt not in seen_types:
                goals.append(_goal(sq, tt, entity, zone))
                seen_types.add(tt)
        # If both sub-questions inferred the same type, add a complementary goal
        if len(goals) == 1:
            complement = "narrative" if goals[0]["tool_type"] == "statistical" else "statistical"
            goals.append(_goal(question, complement, entity, zone))
        return goals

    # ------------------------------------------------------------------
    # 3. Multiple sub_intents detected by normalizer
    #    e.g. sub_intents = ["statistical", "narrative"]
    # ------------------------------------------------------------------
    if len(sub_intents) > 1:
        seen_types: set[str] = set()
        for si in sub_intents:
            # Map intent names to tool_type names
            tt = "current" if si == "current" else (
                 "narrative" if si in ("narrative", "causal") else
                 "statistical" if si == "statistical" else
                 "narrative")
            if tt not in seen_types:
                goals.append(_goal(
                    f"Answer the {si} component of: {question}",
                    tt, entity, zone,
                ))
                seen_types.add(tt)
        return goals

    # ------------------------------------------------------------------
    # 4. Comparative: needs stats for each entity + narrative context
    # ------------------------------------------------------------------
    if intent == "comparative":
        if len(entities) >= 2:
            for ent in entities[:2]:
                goals.append(_goal(
                    f"Retrieve statistics for {ent}", "statistical", ent, zone,
                ))
        else:
            goals.append(_goal(
                "Retrieve comparative statistics", "statistical", entity, zone,
            ))
        goals.append(_goal(
            "Retrieve analyst commentary for context", "narrative", entity, min(zone, 2),
        ))
        return goals

    # ------------------------------------------------------------------
    # 5. Causal: needs narrative (explanation) + statistical (evidence)
    # ------------------------------------------------------------------
    if intent == "causal":
        goals.append(_goal(
            "Retrieve analyst commentary explaining the cause",
            "narrative", entity, min(zone, 2),
        ))
        goals.append(_goal(
            "Retrieve supporting statistics",
            "statistical", entity, min(zone, 2),
        ))
        return goals

    # ------------------------------------------------------------------
    # 6. Zone 3 (current/live): web first, optionally supplement with stats
    # ------------------------------------------------------------------
    if zone == 3:
        goals.append(_goal(
            f"Retrieve current live information about {entity or question}",
            "current", entity, 3,
        ))
        if "statistical" in sub_intents or any(k in q_lower for k in _STAT_KW):
            goals.append(_goal(
                f"Supplement with historical IPL statistics for {entity or question}",
                "statistical", entity, 2,
            ))
        return goals

    # ------------------------------------------------------------------
    # 7. Single-intent question — one goal
    # ------------------------------------------------------------------
    tool_type = _infer_tool_type(question)
    goals.append(_goal(question, tool_type, entity, zone))
    return goals


# ---------------------------------------------------------------------------
# Goal updater — called after every tool result
# ---------------------------------------------------------------------------

def update_goals(goals: list[dict], tool_name: str, result: dict) -> list[dict]:
    """
    Close the first OPEN goal whose tool_type matches the tool that just ran,
    but only if the result actually contains usable content.
    """
    result_type = _tool_type_used(tool_name)
    for goal in goals:
        if goal["status"] == "OPEN" and goal["tool_type"] == result_type:
            if _has_content(result):
                goal["status"]       = "CLOSED"
                goal["evidence_key"] = tool_name
            # Even if no content, don't retry the same tool type endlessly —
            # mark as attempted so the router moves on.
            break
    return goals