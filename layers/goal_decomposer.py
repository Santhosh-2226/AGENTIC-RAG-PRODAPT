"""
layers/goal_decomposer.py

Breaks the normalized question into trackable sub-goals.
Each sub-goal has a tool_type, status (OPEN/CLOSED), and entity.
The sufficiency checker won't pass until all sub-goals are CLOSED.

This is the key layer that separates goal-oriented retrieval
from simple keyword search — the agent knows what it still needs.
"""


def decompose_goals(normalized: dict) -> list:
    """
    Returns list of sub-goal dicts.
    Each: { description, tool_type, entity, zone, status, evidence_key }
    """
    goals = []
    intent = normalized["intent"]
    entities = normalized["entities"]
    zone = normalized["zone"]
    sub_questions = normalized["sub_questions"]

    # ── Comparative: one goal per entity ─────────────────────────────────
    # e.g. "Compare Bumrah and Shami" → two statistical goals + one narrative
    if intent == "comparative" and len(entities) >= 2:
        for entity in entities[:2]:  # max 2 entities for comparison
            goals.append(_make_goal(
                description=f"Retrieve statistics for {entity}",
                tool_type="statistical",
                entity=entity,
                zone=zone
            ))
        goals.append(_make_goal(
            description="Retrieve analyst commentary comparing both players/teams",
            tool_type="narrative",
            entity=None,
            zone=min(zone, 2)  # commentary from corpus, not web
        ))
        return goals

    # ── Compound question: one goal per sub-question ──────────────────────
    # e.g. "What were Kohli's runs AND what did analysts say about his form?"
    if sub_questions and len(sub_questions) == 2:
        for sq in sub_questions:
            tool_type = _infer_tool_type(sq)
            entity = entities[0] if entities else None
            goals.append(_make_goal(
                description=sq,
                tool_type=tool_type,
                entity=entity,
                zone=zone
            ))
        return goals

    # ── Causal: needs analyst commentary + supporting stats ───────────────
    # e.g. "Why did RCB lose so many matches?"
    if intent == "causal":
        entity = entities[0] if entities else None
        goals.append(_make_goal(
            description="Retrieve analyst commentary explaining the cause",
            tool_type="narrative",
            entity=entity,
            zone=min(zone, 2)
        ))
        goals.append(_make_goal(
            description="Retrieve supporting statistics to back the explanation",
            tool_type="statistical",
            entity=entity,
            zone=min(zone, 2)
        ))
        return goals

    # ── Zone 3 (current/live): web first, corpus supplements ─────────────
    # e.g. "Who is the current CSK captain?"
    if zone == 3:
        entity = entities[0] if entities else None
        goals.append(_make_goal(
            description="Retrieve current live information from web search",
            tool_type="current",
            entity=entity,
            zone=3
        ))
        # Only add corpus supplement if question also has a statistical aspect
        if intent == "statistical":
            goals.append(_make_goal(
                description="Supplement with historical statistics from corpus",
                tool_type="statistical",
                entity=entity,
                zone=2
            ))
        return goals

    # ── Default: single goal ──────────────────────────────────────────────
    tool_type = _infer_tool_type(normalized["question"])
    entity = entities[0] if entities else None
    goals.append(_make_goal(
        description=normalized["question"],
        tool_type=tool_type,
        entity=entity,
        zone=zone
    ))
    return goals


def update_goals(goals: list, tool_name: str, result: dict) -> list:
    """
    Called after each tool execution.
    Marks matching OPEN goals as CLOSED if result is non-empty.
    """
    tool_to_type = {
        "search_docs": "narrative",
        "query_data": "statistical",
        "web_search": "current"
    }
    result_type = tool_to_type.get(tool_name)

    for goal in goals:
        if goal["status"] != "OPEN":
            continue
        if goal["tool_type"] != result_type:
            continue
        # Only close if result has real content (no error, non-empty)
        if _result_has_content(result):
            goal["status"] = "CLOSED"
            goal["evidence_key"] = tool_name
            break  # Close one goal per tool call

    return goals


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_goal(description: str, tool_type: str,
               entity, zone: int) -> dict:
    return {
        "description": description,
        "tool_type": tool_type,    # "statistical" | "narrative" | "current"
        "entity": entity,
        "zone": zone,
        "status": "OPEN",          # "OPEN" | "CLOSED"
        "evidence_key": None       # set when closed
    }


def _infer_tool_type(text: str) -> str:
    """Infer whether a question needs stats or narrative."""
    statistical_kw = [
        "runs", "wickets", "average", "rate", "score",
        "most", "highest", "total", "how many", "stats",
        "economy", "strike rate", "innings", "overs"
    ]
    t = text.lower()
    if any(k in t for k in statistical_kw):
        return "statistical"
    return "narrative"


def _result_has_content(result: dict) -> bool:
    """True if a tool result has usable content."""
    if not result or "error" in result:
        return False
    # search_docs: needs at least one chunk
    if "chunks" in result:
        return len(result["chunks"]) > 0
    # query_data: needs at least one row
    if "rows" in result:
        return result.get("row_count", 0) > 0
    # web_search: needs at least one result
    if "results" in result:
        return len(result["results"]) > 0
    return False