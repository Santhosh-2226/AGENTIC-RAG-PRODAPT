"""
layers/citation.py

Binds every claim to an exact source from evidence memory.
No LLM-generated citations — only what was actually retrieved.
Statistical claim → table + SQL.
Documentary claim → filename + page.
Web claim → URL + date.
"""

from memory.evidence import EvidenceMemory


def bind_citations(answer_draft: dict, memory: EvidenceMemory) -> dict:
    """
    Attach exact citation strings to the answer draft.
    Returns updated answer_draft with 'citations' list populated.
    """
    citations = []
    all_sources = memory.all_sources()

    for source in all_sources:
        if source["type"] == "document":
            citation = (
                f"search_docs → {source['source']}, "
                f"page {source['page']} (IPL {source['season']})"
            )
            if citation not in citations:
                citations.append(citation)

        elif source["type"] == "database":
            citation = (
                f"query_data → {source['table']} table "
                f"({source['row_count']} rows matched)"
            )
            if citation not in citations:
                citations.append(citation)

        elif source["type"] == "web":
            citation = (
                f"web_search → {source['url']} "
                f"(published {source['date']})"
            )
            if citation not in citations:
                citations.append(citation)

    answer_draft["citations"] = citations
    return answer_draft