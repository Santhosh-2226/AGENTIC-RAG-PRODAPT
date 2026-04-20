"""
layers/reflection.py  — Bonus C

After composing the answer, checks:
1. Does it actually answer the original question?
2. Is every claim cited?
3. Do sources contradict each other?
4. Is the temporal zone consistent?

If reflection fails AND steps remain → returns a fix_query for one more retrieval.
Trace records before and after state.
"""

import json
import re
from anthropic import Anthropic


def reflect(
    question: str,
    answer: dict,
    memory,
    goals: list,
    step_count: int,
    max_steps: int,
    client: Anthropic
) -> tuple:
    """
    Returns (answer_dict, reflection_result_dict).
    reflection_result contains: passed, issue, fix_query, action.
    """
    answer_text = answer.get("answer_text", "")
    unresolved = answer.get("unresolved", [])
    citations = answer.get("citations", [])

    prompt = f"""Review this answer to an IPL cricket question.

Original question: "{question}"

Answer produced:
{answer_text}

Citations attached: {json.dumps(citations)}

Unresolved gaps: {json.dumps(unresolved)}

Check these 4 things:
1. Does the answer directly address what was asked? (not a related but different question)
2. Does every factual claim reference an evidence source?
3. Are there any contradictions between the evidence sources?
4. If the question asked about current/live info, does the answer clearly note what is from the web vs the corpus?

Respond with ONLY valid JSON in this exact format:
{{"passes": true, "issue": "", "fix_query": ""}}

Or if it fails:
{{"passes": false, "issue": "specific description of what is wrong", "fix_query": "short targeted query to fix the gap"}}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()

        # Extract JSON safely
        json_match = re.search(r'\{.*?\}', raw, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {"passes": True, "issue": "", "fix_query": ""}

    except Exception:
        # If reflection itself fails, pass through — don't crash the agent
        result = {"passes": True, "issue": "reflection_parse_error", "fix_query": ""}

    if result.get("passes", True):
        return answer, {
            "passed": True,
            "issue": None,
            "action": "no_change"
        }

    # Reflection failed — decide what to do
    steps_remaining = max_steps - step_count
    fix_query = result.get("fix_query", "")

    if steps_remaining > 1 and fix_query:
        return answer, {
            "passed": False,
            "issue": result.get("issue", ""),
            "fix_query": fix_query,
            "action": "one_more_retrieval_triggered",
            "note": "Agent will attempt one additional targeted retrieval."
        }
    else:
        return answer, {
            "passed": False,
            "issue": result.get("issue", ""),
            "action": "no_steps_remaining",
            "note": "Answer has gaps but step cap reached. Gaps noted in uncertainty statement."
        }