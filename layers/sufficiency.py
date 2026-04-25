"""
layers/sufficiency.py
Returns True only when all sub-goals are closed.
"""
from memory.evidence import EvidenceMemory


def is_sufficient(goals: list, normalized: dict, memory: EvidenceMemory) -> bool:
    open_goals = [g for g in goals if g.get("status") == "OPEN"]

    has_usable_evidence = False

    for tool in ("query_data", "search_docs", "web_search"):
        for item in memory.get_by_tool(tool):
            result = item.get("result", {})
            if isinstance(result, dict) and not result.get("error"):
                if result.get("row_count", 1) != 0:
                    has_usable_evidence = True
                    break
        if has_usable_evidence:
            break

    return (not open_goals) and has_usable_evidence