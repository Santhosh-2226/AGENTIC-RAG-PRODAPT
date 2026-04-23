"""
layers/citation.py

Binds every claim to an exact source from evidence memory.
No LLM-generated citations — only what was actually retrieved.
Statistical claim → table + SQL.
Documentary claim → filename + page.
Web claim → URL + date.
"""

from memory.evidence import EvidenceMemory


def bind_citations(answer_draft, memory: EvidenceMemory):
    """
    Attach exact citation strings to the answer draft.
    Accepts str or dict. Always returns dict with 'citations' list populated.
    """
    # Normalise — composer sometimes returns a plain string
    if isinstance(answer_draft, str):
        answer_draft = {"final_answer": answer_draft, "citations": []}

    citations = []
    all_sources = memory.all_sources()

    for source in all_sources:
        if source.get("type") == "document":
            citation = (
                f"search_docs → {source.get('source', 'unknown')}, "
                f"page {source.get('page', '?')} (IPL {source.get('season', '?')})"
            )
            if citation not in citations:
                citations.append(citation)

        elif source.get("type") == "database":
            citation = (
                f"query_data → {source.get('table', 'unknown')} table "
                f"({source.get('row_count', '?')} rows matched)"
            )
            if citation not in citations:
                citations.append(citation)

        elif source.get("type") == "web":
            citation = (
                f"web_search → {source.get('url', 'unknown')} "
                f"(published {source.get('date', '?')})"
            )
            if citation not in citations:
                citations.append(citation)

    answer_draft["citations"] = citations
    return answer_draft