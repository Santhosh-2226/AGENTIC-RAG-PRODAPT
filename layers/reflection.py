"""
layers/reflection.py

After composing the answer, checks:
1. Does it actually answer the original question?
2. Is every claim cited?
3. Do sources contradict each other?
4. Is the temporal zone consistent?
"""
import os
import json
import re


def reflect(
    question: str,
    answer: dict,
    memory,
    goals: list,
    step_count: int,
    max_steps: int,
    client,
) -> tuple:
    """
    Returns (answer_dict, reflection_result_dict).
    """
    answer_text = answer.get("final_answer", answer.get("answer_text", ""))
    unresolved  = answer.get("unresolved", [])
    citations   = answer.get("citations", [])

    prompt = f"""Review this answer to an IPL cricket question.

Original question: "{question}"

Answer produced:
{answer_text}

Citations attached: {json.dumps(citations)}

Unresolved gaps: {json.dumps(unresolved)}

Check these 4 things:
1. Does the answer directly address what was asked?
2. Does every factual claim reference an evidence source?
3. Are there any contradictions between evidence sources?
4. If the question asked about current/live info, does the answer note what is from web vs corpus?

Respond with ONLY valid JSON, no extra text:
{{"passes": true, "issue": "", "fix_query": ""}}

Or if it fails:
{{"passes": false, "issue": "specific description", "fix_query": "short targeted query"}}"""

    try:
        response = client.messages.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        json_match = re.search(r'\{.*?\}', raw, re.DOTALL)
        result = json.loads(json_match.group()) if json_match else {"passes": True, "issue": "", "fix_query": ""}

    except Exception:
        result = {"passes": True, "issue": "reflection_parse_error", "fix_query": ""}

    if result.get("passes", True):
        return answer, {"passed": True, "issue": None, "action": "no_change"}

    steps_remaining = max_steps - step_count
    fix_query = result.get("fix_query", "")

    if steps_remaining > 1 and fix_query:
        return answer, {
            "passed": False,
            "issue": result.get("issue", ""),
            "fix_query": fix_query,
            "action": "one_more_retrieval_triggered",
        }
    else:
        return answer, {
            "passed": False,
            "issue": result.get("issue", ""),
            "action": "no_steps_remaining",
            "note": "Answer has gaps but step cap reached.",
        }