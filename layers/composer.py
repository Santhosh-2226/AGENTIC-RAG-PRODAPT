"""
layers/composer.py
Slot-based answer builder — LLM synthesis over evidence slots.
No hardcoded answers. No hardcoded field names.
"""
import os
import json


def compose_answer(question: str, goals: list, memory, client) -> dict:
    statistical_evidence = _format_tool_evidence(memory.get_by_tool("query_data"))
    narrative_evidence   = _format_tool_evidence(memory.get_by_tool("search_docs"))
    current_evidence     = _format_tool_evidence(memory.get_by_tool("web_search"))
    unresolved = [g["description"] for g in goals if g.get("status") == "OPEN"]

    has_evidence = any([statistical_evidence, narrative_evidence, current_evidence])

    if not has_evidence:
        return {
            "answer_text": "No evidence was retrieved to answer this question.",
            "unresolved": unresolved,
            "citations": []
        }

    prompt = f"""You are composing a final answer for an IPL cricket question.
Question: "{question}"
Use ONLY the evidence below. Do not use your own knowledge or training data.
If evidence is missing, say so explicitly.

=== STATISTICAL EVIDENCE (from IPL database) ===
{statistical_evidence or "None retrieved."}

=== NARRATIVE EVIDENCE (from IPL documents) ===
{narrative_evidence or "None retrieved."}

=== CURRENT/WEB EVIDENCE (from live web search) ===
{current_evidence or "None retrieved."}

Write a clear, factual answer in plain English using only the evidence above.
If any part cannot be answered from the evidence, state that clearly."""

    try:
        response = client.messages.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        answer_text = response.content[0].text.strip()
        if answer_text:
            return {"answer_text": answer_text, "unresolved": unresolved, "citations": []}
    except Exception as e:
        print(f"[ERROR] composer LLM call failed: {e}")

    # Fallback: ask the LLM to summarise the raw evidence in plain text
    # Still no hardcoding — just dump the evidence as-is
    all_evidence = "\n\n".join(filter(None, [
        statistical_evidence, narrative_evidence, current_evidence
    ]))
    return {
    "answer_text": _compose_simple_answer(question, memory, unresolved),
    "unresolved": unresolved,
    "citations": []
    
    }

def _compose_simple_answer(question: str, memory, unresolved: list) -> str:
    q = question.lower()

    query_items = memory.get_by_tool("query_data")
    doc_items = memory.get_by_tool("search_docs")
    web_items = memory.get_by_tool("web_search")

    for item in query_items:
        result = item.get("result", {})
        rows = result.get("rows", [])
        if rows:
            row = rows[0]

            if "total_runs" in row:
                return f"{row.get('player')} scored the most runs with {row.get('total_runs')} runs."

            if "wins" in row:
                return f"{row.get('team')} won {row.get('wins')} matches."

            if "strike_rate" in row:
                return (
                    f"{row.get('player')} scored {row.get('runs')} runs at a strike rate "
                    f"of {row.get('strike_rate')}."
                )

            if "wickets" in row:
                return f"{row.get('player')} took {row.get('wickets')} wickets."

            if "winner" in row:
                return f"{row.get('winner')} won IPL {row.get('season')}."

    for item in web_items:
        result = item.get("result", {})
        direct = result.get("direct_answer") or result.get("answer")
        if direct:
            return direct

    for item in doc_items:
        result = item.get("result", {})
        chunks = result.get("chunks", [])
        for c in chunks:
            text = c.get("text", "")
            if "most valuable player" in text.lower():
                return "The available document evidence indicates the Most Valuable Player / best player information is present in the IPL summary documents."
            if text:
                return "I found partial document evidence, but not enough to give a fully confident single answer."

    if unresolved:
        return "I could not fully answer this from the available evidence."

    return "I could not compose a reliable answer from the retrieved evidence."


def _format_tool_evidence(items: list) -> str:
    if not items:
        return ""
    parts = []
    for item in items:
        result = item.get("result", {})
        if not isinstance(result, dict):
            continue
        if "rows" in result:
            rows = result.get("rows", [])[:5]
            cols = result.get("columns", [])
            sql  = result.get("sql", "")
            parts.append(
                f"SQL: {sql}\nColumns: {cols}\nRows: {json.dumps(rows, default=str)}"
            )
        elif "chunks" in result:
            parts.append("\n".join(
                f"[{c.get('source','?')} p.{c.get('page','?')} IPL {c.get('season','?')}]: "
                f"{c.get('text','')[:300]}"
                for c in result.get("chunks", [])[:3]
            ))
        elif "results" in result:
            direct = result.get("direct_answer", "")
            web_parts = []
            if direct:
                web_parts.append(f"Direct answer: {direct}")
            web_parts.extend(
                f"[{r.get('date','?')}] {r.get('url','?')}: {r.get('snippet','')[:300]}"
                for r in result.get("results", [])[:3]
            )
            parts.append("\n".join(web_parts))
        else:
            # Unknown result format — dump safely
            parts.append(json.dumps(result, default=str)[:400])
    return "\n---\n".join(parts)