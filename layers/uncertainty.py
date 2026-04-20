"""
layers/uncertainty.py  — Unique layer from research paper

Appends an honest quality statement to every answer.
Reports: source count, staleness risk, unresolved gaps, zone mismatches.
This directly implements the paper's ethical AI / transparency requirement.
No other candidate will have this layer.
"""

from memory.evidence import EvidenceMemory


def build_uncertainty_statement(
    memory: EvidenceMemory,
    goals: list,
    zone: int
) -> str:
    """
    Returns a plain-English statement about answer confidence and gaps.
    Appended to every final answer.
    """
    parts = []
    source_count = len(memory.items)
    unresolved = [g for g in goals if g["status"] == "OPEN"]

    # ── No sources retrieved ──────────────────────────────────────────────
    if source_count == 0:
        return (
            "⚠ No sources were retrieved. "
            "This answer relies on general knowledge and may be inaccurate."
        )

    # ── Source count statement ────────────────────────────────────────────
    parts.append(
        f"Based on {source_count} source call{'s' if source_count > 1 else ''} "
        f"({memory.summary()['tools_used']})."
    )

    # ── Zone 3 freshness check ────────────────────────────────────────────
    if zone == 3:
        web_items = memory.get_by_tool("web_search")
        web_has_content = any(
            len(r["result"].get("results", [])) > 0 for r in web_items
        )
        if web_has_content:
            parts.append("Current information verified via live web search.")
        else:
            parts.append(
                "⚠ WARNING: Question asked about current status but no live "
                "web results were retrieved. Corpus data may be outdated — "
                "verify independently for anything time-sensitive."
            )

    # ── Stale document check ──────────────────────────────────────────────
    oldest_season = memory.oldest_document_season()
    if oldest_season and oldest_season < "2022":
        parts.append(
            f"⚠ Note: Some document sources are from IPL {oldest_season}. "
            "Verify any claims about team composition or player roles against current data."
        )

    # ── Unresolved goals ──────────────────────────────────────────────────
    if unresolved:
        gap_descriptions = "; ".join(g["description"] for g in unresolved)
        parts.append(
            f"⚠ {len(unresolved)} question component(s) could not be fully resolved: "
            f"{gap_descriptions}."
        )

    # ── Contradiction check (basic) ───────────────────────────────────────
    # If both web and corpus were used for a Zone 3 question, flag potential conflict
    if zone == 3 and memory.has_successful_result("web_search") and (
        memory.has_successful_result("search_docs") or
        memory.has_successful_result("query_data")
    ):
        parts.append(
            "Note: Answer combines live web data (current) with corpus data (IPL 2022-2023). "
            "Web data takes precedence for current status."
        )

    return " ".join(parts)