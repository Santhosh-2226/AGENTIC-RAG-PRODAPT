"""
layers/composer.py

Slot-based answer builder.
Statistical slot ← query_data only.
Narrative slot ← search_docs only.
Current slot ← web_search only.

Claude Haiku synthesizes across populated slots.
Never fills a slot from its own training knowledge.
Unresolved sub-goals are explicitly noted as gaps.
"""

import json
from anthropic import Anthropic


def compose_answer(question: str, goals: list, memory, client: Anthropic) -> dict:
    """
    Build final answer from evidence slots only.
    Returns dict with answer_text, slots, unresolved list.
    """
    # ── Populate slots from memory ────────────────────────────────────────
    statistical_evidence = _format_tool_evidence(memory.get_by_tool("query_data"))
    narrative_evidence = _format_tool_evidence(memory.get_by_tool("search_docs"))
    current_evidence = _format_tool_evidence(memory.get_by_tool("web_search"))

    unresolved = [g["description"] for g in goals if g["status"] == "OPEN"]

    # ── Build synthesis prompt ────────────────────────────────────────────
    prompt = f"""You are composing a final answer for an IPL cricket question.

Question: "{question}"

Use ONLY the evidence provided below. Do not use your own knowledge or training data.
Every factual claim must come from one of the evidence slots.
If evidence is missing for part of the question, say so explicitly.

=== STATISTICAL EVIDENCE (from IPL database) ===
{statistical_evidence or "No statistical data retrieved."}

=== NARRATIVE EVIDENCE (from IPL documents) ===
{narrative_evidence or "No document evidence retrieved."}

=== CURRENT/LIVE EVIDENCE (from web search) ===
{current_evidence or "No live web data retrieved."}

=== UNRESOLVED GAPS ===
{chr(10).join(f"- {u}" for u in unresolved) if unresolved else "None — all goals resolved."}

Instructions:
- Write a clear, factual answer in plain English.
- For each claim, note the source slot in parentheses: (database), (document: filename p.X), (web: URL).
- If unresolved gaps exist, end with: "Note: [gap description] could not be confirmed from available sources."
- Do not speculate beyond the evidence."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )

    return {
        "answer_text": response.content[0].text,
        "statistical_slot": statistical_evidence,
        "narrative_slot": narrative_evidence,
        "current_slot": current_evidence,
        "unresolved": unresolved,
        "citations": []   # filled by citation binder
    }


def _format_tool_evidence(items: list) -> str:
    if not items:
        return ""
    parts = []
    for item in items:
        input_str = json.dumps(item["input"])
        result = item["result"]

        # Format differently per tool type
        if "chunks" in result:  # search_docs
            chunk_texts = []
            for chunk in result.get("chunks", [])[:3]:
                chunk_texts.append(
                    f"[{chunk.get('source', '?')} p.{chunk.get('page', '?')} "
                    f"IPL {chunk.get('season', '?')}]: {chunk.get('text', '')[:200]}"
                )
            parts.append("Input: " + input_str + "\n" + "\n".join(chunk_texts))

        elif "rows" in result:  # query_data
            rows_preview = json.dumps(result.get("rows", [])[:5], default=str)
            parts.append(
                f"SQL: {result.get('sql', '')}\n"
                f"Table: {result.get('table', '?')}\n"
                f"Rows ({result.get('row_count', 0)} total): {rows_preview}"
            )

        elif "results" in result:  # web_search
            web_texts = []
            for r in result.get("results", [])[:3]:
                web_texts.append(
                    f"[{r.get('date', '?')}] {r.get('url', '?')}: {r.get('snippet', '')[:200]}"
                )
            parts.append("Query: " + input_str + "\n" + "\n".join(web_texts))

        else:
            parts.append(f"Input: {input_str}\nResult: {json.dumps(result, default=str)[:200]}")

    return "\n---\n".join(parts)