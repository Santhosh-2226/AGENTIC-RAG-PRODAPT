"""
layers/sufficiency.py

Checks after every tool call whether enough evidence exists to answer.
Returns True only when ALL sub-goals are CLOSED.
Zone 3 questions additionally require a web result before passing.
Comparative questions require both entities to be resolved.

This is what prevents gold-plating (unnecessary extra calls)
and also what prevents premature exit (stopping too early).
"""

from memory.evidence import EvidenceMemory


def is_sufficient(goals: list, normalized: dict, memory: EvidenceMemory) -> bool:
    """
    Returns True if the agent has enough evidence to compose a final answer.
    Returns False if more tool calls are needed.
    """
    open_goals = [g for g in goals if g["status"] == "OPEN"]

    # ── All goals resolved → sufficient ──────────────────────────────────
    if not open_goals:
        return True

    # ── Zone 3: must have web result before declaring sufficient ──────────
    # Even if all corpus goals are closed, a "current" question needs web data
    if normalized["zone"] == 3:
        web_results = memory.get_by_tool("web_search")
        web_has_content = any(
            len(r["result"].get("results", [])) > 0
            for r in web_results
        )
        if not web_has_content:
            return False

    # ── Comparative: both entities need data ──────────────────────────────
    if normalized["intent"] == "comparative":
        entities = normalized.get("entities", [])
        if len(entities) >= 2:
            # Check that statistical goals for both entities are closed
            stats_goals = [g for g in goals if g["tool_type"] == "statistical"]
            open_stats = [g for g in stats_goals if g["status"] == "OPEN"]
            if open_stats:
                return False

    # ── Still have open goals → not sufficient ────────────────────────────
    if open_goals:
        return False

    return True