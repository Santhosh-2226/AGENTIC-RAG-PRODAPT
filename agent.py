"""
agent.py — The core agent loop.

Every line is yours. Every decision is explainable.
ReAct pattern: Reason (tool selector) → Act (call tool) → Observe (evidence memory) → Repeat.
Hard cap: 8 tool calls. Enforced in code. Raises CapExceeded if hit by a looping question.
"""

import json
import hashlib
import time
from anthropic import Anthropic

from memory.evidence import EvidenceMemory
from layers.gatekeeper import gatekeeper_check
from layers.normalizer import normalize_query
from layers.goal_decomposer import decompose_goals, update_goals
from layers.sufficiency import is_sufficient
from layers.composer import compose_answer
from layers.citation import bind_citations
from layers.reflection import reflect
from layers.uncertainty import build_uncertainty_statement
from utils.cache import load_cache, save_cache
from utils.tracer import Tracer
from tools.search_docs import search_docs
from tools.query_data import query_data
from tools.web_search import web_search

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_STEPS = 8
MAX_WEB_CALLS = 2

# ── Tool definitions — written for the LLM, not for humans ───────────────────
TOOL_DEFINITIONS = [
    {
        "name": "search_docs",
        "description": (
            "Search IPL match reports, season reviews, player profiles, and expert commentary "
            "stored as PDF documents. Use when the question asks for narrative explanation, "
            "analyst opinion, tactical analysis, or historical context. "
            "Do NOT use for precise statistics or numbers — use query_data instead. "
            "Do NOT use for current/live/recent information — use web_search instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language search query"},
                "season": {"type": "string", "description": "Optional: '2022' or '2023'"},
                "entity": {"type": "string", "description": "Optional: player or team name"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_data",
        "description": (
            "Query the IPL 2022-2023 structured statistics database. Use when the question "
            "asks for runs, wickets, averages, strike rates, economy rates, match results, "
            "rankings, or any measurable number. "
            "Do NOT use for opinions or narrative — use search_docs instead. "
            "Do NOT use for events after IPL 2023 — use web_search instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Plain English stats question"},
                "table_hint": {
                    "type": "string",
                    "description": "Optional: 'batting', 'bowling', 'matches', 'players'"
                }
            },
            "required": ["question"]
        }
    },
    {
        "name": "web_search",
        "description": (
            "Search the live web. Use ONLY when the question asks about current, recent, "
            "or live information: current captain, today's news, injury updates, "
            "retirement status, 2024/2025 season info. "
            "Do NOT use for historical data available in the corpus. "
            "Maximum 2 calls per question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Short query, under 10 words"},
                "reason": {"type": "string", "description": "Why live data is needed here"}
            },
            "required": ["query", "reason"]
        }
    }
]

TOOL_DISPATCH = {
    "search_docs": search_docs,
    "query_data": query_data,
    "web_search": web_search
}

client = Anthropic()


class CapExceededError(Exception):
    """Raised when agent hits the 8-call hard cap."""
    pass


def run_agent(user_question: str) -> dict:
    """
    Main entry point. Runs all 12 layers for one question.
    Returns dict: final_answer, citations, steps_used, status, uncertainty, trace path.
    """
    tracer = Tracer(user_question)

    # ── L1: Cache ─────────────────────────────────────────────────────────
    cached = load_cache(user_question)
    if cached:
        tracer.log_cache_hit()
        return cached

    # ── L2: Gatekeeper ────────────────────────────────────────────────────
    gate = gatekeeper_check(user_question)
    if gate["action"] == "direct_answer":
        return tracer.finalize(gate["answer"], [], "direct_answer", steps_used=0)
    if gate["action"] == "refuse":
        return tracer.finalize(gate["answer"], [], "refused", steps_used=0)

    # ── L3: Query normalization ───────────────────────────────────────────
    normalized = normalize_query(user_question)
    if normalized["scope_trap"]:
        return tracer.finalize(
            normalized["scope_trap_response"], [], "scope_clarification", steps_used=0
        )

    # ── L4: Goal decomposition ────────────────────────────────────────────
    goals = decompose_goals(normalized)

    # ── L5: Planning step (Bonus A) ───────────────────────────────────────
    plan = _build_plan(normalized, goals)
    tracer.log_plan(plan)

    # ── L6: Agent loop — the core ─────────────────────────────────────────
    memory = EvidenceMemory()
    messages = _initial_messages(normalized["question"], plan)
    step = 0
    web_calls = 0

    while step < MAX_STEPS:
        # Choose available tools (remove web_search once cap hit)
        available_tools = (
            TOOL_DEFINITIONS if web_calls < MAX_WEB_CALLS
            else [t for t in TOOL_DEFINITIONS if t["name"] != "web_search"]
        )

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",  # cheap for all reasoning steps
            max_tokens=512,
            tools=available_tools,
            messages=messages
        )

        # Claude decided no tool needed — exit loop
        if response.stop_reason == "end_turn":
            break

        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if not tool_use:
            break

        tool_name = tool_use.name
        tool_input = tool_use.input

        # Duplicate guard — block same (tool, input) combination
        call_hash = hashlib.md5(
            f"{tool_name}{json.dumps(tool_input, sort_keys=True)}".encode()
        ).hexdigest()
        if memory.is_duplicate(call_hash):
            tracer.log_duplicate_blocked(tool_name, tool_input)
            messages = _add_tool_result(messages, response, tool_use.id,
                                        "DUPLICATE_CALL: already tried this. Use a different approach.")
            step += 1
            continue

        # Zone 3 enforcement — web must fire before corpus for current questions
        if normalized["zone"] == 3 and tool_name != "web_search" and web_calls == 0:
            tracer.log_zone_override(tool_name)
            messages = _add_tool_result(messages, response, tool_use.id,
                                        "ZONE_RULE: This question needs current info. Call web_search first.")
            step += 1
            continue

        # Web cap enforcement
        if tool_name == "web_search":
            if web_calls >= MAX_WEB_CALLS:
                messages = _add_tool_result(messages, response, tool_use.id,
                                            "WEB_CAP: Maximum 2 web searches reached. Use corpus tools only.")
                step += 1
                continue
            web_calls += 1

        # Execute tool with error handling (retry once on failure)
        start = time.time()
        try:
            result = TOOL_DISPATCH[tool_name](**tool_input)
            success = True
        except Exception as e:
            tracer.log_tool_error(tool_name, tool_input, str(e))
            # Retry once with same input
            try:
                result = TOOL_DISPATCH[tool_name](**tool_input)
                success = True
            except Exception as e2:
                result = {"error": str(e2), "tool": tool_name}
                success = False

        latency_ms = int((time.time() - start) * 1000)

        # Store evidence, mark hash used
        memory.add(tool_name, tool_input, result, call_hash)
        memory.mark_duplicate(call_hash)

        # Update goal statuses
        goals = update_goals(goals, tool_name, result)

        # Log step (includes Bonus B telemetry)
        tracer.log_step(step + 1, tool_name, tool_input, result, latency_ms, success)

        # Feed result back into conversation
        messages = _add_tool_result(messages, response, tool_use.id, result)
        step += 1

        # Early exit if all goals resolved
        if is_sufficient(goals, normalized, memory):
            break

    # Hard cap check — if all 8 steps used and still open goals, structured refusal
    open_goals = [g for g in goals if g["status"] == "OPEN"]
    if step >= MAX_STEPS and open_goals:
        refusal = (
            f"I searched IPL match documents, statistical records, and live web sources "
            f"across {MAX_STEPS} attempts but could not fully resolve: "
            f"{'; '.join(g['description'] for g in open_goals)}. "
            f"This may be outside the IPL 2022-2023 coverage of this system."
        )
        return tracer.finalize(refusal, [], "cap_exceeded", steps_used=step)

    # ── L7: Answer composition ────────────────────────────────────────────
    answer_draft = compose_answer(normalized["question"], goals, memory, client)

    # ── L8: Citation binding ──────────────────────────────────────────────
    answer_with_citations = bind_citations(answer_draft, memory)

    # ── L9: Reflection (Bonus C) ──────────────────────────────────────────
    answer_final, reflection_result = reflect(
        normalized["question"], answer_with_citations,
        memory, goals, step, MAX_STEPS, client
    )

    # ── L10: Uncertainty statement ────────────────────────────────────────
    uncertainty = build_uncertainty_statement(memory, goals, normalized["zone"])

    # ── L11: Trace write ──────────────────────────────────────────────────
    output = tracer.finalize(
        answer=answer_final,
        citations=answer_final.get("citations", []),
        status="answered",
        uncertainty=uncertainty,
        steps_used=step,
        reflection=reflection_result
    )

    # ── L12: Cache store ──────────────────────────────────────────────────
    save_cache(user_question, output)
    return output


# ── Private helpers — explain these line by line in interview ─────────────────

def _build_plan(normalized: dict, goals: list) -> str:
    """Bonus A: 1-3 sentence plan written before any tool call."""
    tools_needed = list(dict.fromkeys(g["tool_type"] for g in goals))  # ordered, no dupes
    type_to_tool = {"statistical": "query_data", "narrative": "search_docs", "current": "web_search"}
    tool_names = [type_to_tool.get(t, t) for t in tools_needed]
    goal_descs = "; ".join(g["description"] for g in goals)
    zone_note = (
        "Web search required first (live/current question)."
        if normalized["zone"] == 3 else
        "Corpus is sufficient (historical question)."
    )
    return (
        f"Plan: Use {', '.join(tool_names)} to answer this {normalized['intent']} question. "
        f"Sub-goals: {goal_descs}. {zone_note}"
    )


def _initial_messages(question: str, plan: str) -> list:
    """Starting conversation for the agent loop."""
    return [{
        "role": "user",
        "content": (
            f"Answer this IPL cricket question: {question}\n\n"
            f"Your plan: {plan}\n\n"
            "Use the tools to retrieve evidence. "
            "Do not answer from your own knowledge. "
            "Every claim in your final answer must come from a tool result."
        )
    }]


def _add_tool_result(messages: list, response, tool_use_id: str, result) -> list:
    """Append assistant tool call + result to message history."""
    messages.append({"role": "assistant", "content": response.content})
    messages.append({
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": json.dumps(result, default=str)
        }]
    })
    return messages