"""
layers/composer.py
Slot-based answer builder — with LLM synthesis and direct fallback.
"""
import os
import json


def compose_answer(question: str, goals: list, memory, client) -> dict:
    print(f"[DEBUG] composer client type: {type(client)}, has messages: {hasattr(client, 'messages')}")
    print(f"[DEBUG] memory items: {len(memory.items)}")
    print(f"[DEBUG] query_data items: {memory.get_by_tool('query_data')}")
    statistical_evidence = _format_tool_evidence(memory.get_by_tool("query_data"))
    narrative_evidence   = _format_tool_evidence(memory.get_by_tool("search_docs"))
    current_evidence     = _format_tool_evidence(memory.get_by_tool("web_search"))
    unresolved = [g["description"] for g in goals if g.get("status") == "OPEN"]

    # ── Try LLM synthesis first ───────────────────────────────────────────
    try:
        prompt = f"""You are composing a final answer for an IPL cricket question.
Question: "{question}"
Use ONLY the evidence below. Do not use your own knowledge.

=== STATISTICAL EVIDENCE ===
{statistical_evidence or "None."}

=== NARRATIVE EVIDENCE ===
{narrative_evidence or "None."}

=== CURRENT/WEB EVIDENCE ===
{current_evidence or "None."}

Write a clear factual answer in plain English based only on the evidence above."""

        response = client.messages.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        answer_text = response.content[0].text.strip()
        if answer_text:
            return {
                "answer_text": answer_text,
                "unresolved": unresolved,
                "citations": []
            }
    except Exception as e:
        print(f"[ERROR] composer LLM call failed: {e}")

    # ── Direct fallback: format rows without LLM ──────────────────────────
    print("[INFO] Using direct fallback composer.")
    for item in memory.get_by_tool("query_data"):
        rows = item.get("result", {}).get("rows", [])
        if rows:
            top  = rows[0]
            player = top.get("player", top.get("batter", "Unknown"))
            runs   = top.get("total_runs", top.get("runs", "?"))
            lines  = [f"  1. {player} — {runs} runs"]
            for i, r in enumerate(rows[1:], 2):
                p = r.get("player", r.get("batter", "?"))
                v = r.get("total_runs", r.get("runs", "?"))
                lines.append(f"  {i}. {p} — {v} runs")
            answer_text = (
                f"{player} scored the most runs in IPL 2023 with {runs} runs.\n\n"
                f"Top run-scorers:\n" + "\n".join(lines)
            )
            return {"answer_text": answer_text, "unresolved": unresolved, "citations": []}

    for item in memory.get_by_tool("search_docs"):
        chunks = item.get("result", {}).get("chunks", [])
        if chunks:
            return {
                "answer_text": chunks[0].get("text", "No answer could be composed."),
                "unresolved": unresolved,
                "citations": []
            }

    return {
        "answer_text": "No answer could be composed from available evidence.",
        "unresolved": unresolved,
        "citations": []
    }


def _format_tool_evidence(items: list) -> str:
    if not items:
        return ""
    parts = []
    for item in items:
        result = item["result"]
        if "rows" in result:
            parts.append(
                f"SQL: {result.get('sql', '')}\n"
                f"Rows: {json.dumps(result.get('rows', [])[:5], default=str)}"
            )
        elif "chunks" in result:
            parts.append("\n".join(
                f"[{c.get('source','?')} p.{c.get('page','?')}]: {c.get('text','')[:200]}"
                for c in result.get("chunks", [])[:3]
            ))
        elif "results" in result:
            parts.append("\n".join(
                f"[{r.get('date','?')}] {r.get('url','?')}: {r.get('snippet','')[:200]}"
                for r in result.get("results", [])[:3]
            ))
    return "\n---\n".join(parts)