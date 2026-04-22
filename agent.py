"""
agent.py

Custom agent loop for IPL Agentic RAG using Groq.
Hard cap counts REAL tool calls only.

FIXES:
- Uses GroqCompatClient (groq_compat.py) so layer files that call
  client.messages.create() (Anthropic style) work without modification.
- _safe_llm_call: 3-attempt model ladder, all using live non-deprecated models:
    Attempt 1 → llama-3.3-70b-versatile          (primary)
    Attempt 2 → meta-llama/llama-4-scout-17b-16e-instruct (fallback)
    Attempt 3 → llama-3.1-8b-instant, NO tools   (graceful degradation)
- Increased max_completion_tokens to 2048 to prevent mid-JSON truncation.
- _repair_json() + _parse_tool_args() for brace-imbalanced tool arguments.
- model_decommissioned errors caught same as tool_use_failed.
"""

import json
import os
import time
import hashlib
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

# ── Use the compat client so ALL layer files work regardless of SDK style ───
from groq_compat import get_compat_client, GroqCompatClient

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

load_dotenv()

if not os.getenv("GROQ_API_KEY"):
    raise ValueError("GROQ_API_KEY not found in .env")


def get_client() -> GroqCompatClient:
    """Always returns the compat client (supports both .messages and .chat)."""
    return get_compat_client()


MAX_TOOL_CALLS = 8
MAX_WEB_CALLS = 2
MAX_LOOP_TURNS = 16
MAX_COMPLETION_TOKENS = 2048  # raised from 512 — prevents JSON being cut mid-brace

# ── Model ladder ─────────────────────────────────────────────────────────────
MODEL_PRIMARY  = os.getenv("GROQ_MODEL",         "llama-3.3-70b-versatile")
MODEL_FALLBACK = os.getenv("GROQ_FALLBACK_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
MODEL_NOTOOL   = os.getenv("GROQ_NOTOOL_MODEL",   "llama-3.1-8b-instant")
# ─────────────────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "search_docs",
        "description": (
            "Search IPL season reviews, match reports, commentary, and narrative documents. "
            "Use this for explanations, commentary, analysis, reviews, or qualitative context. "
            "Do not use this for precise numeric statistics. "
            "Do not use this for current or live information."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query":  {"type": "string", "description": "Natural language search query"},
                "season": {"type": "string", "description": "Optional season filter such as 2023 or 2024"},
                "entity": {"type": "string", "description": "Optional player or team name"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "query_data",
        "description": (
            "Query the structured IPL statistics database. "
            "Use this for runs, wickets, averages, strike rates, economy, rankings, totals, "
            "match results, and other measurable statistics. "
            "Do not use this for commentary or narrative explanation. "
            "Do not use this for current live information outside the dataset coverage."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question":   {"type": "string", "description": "Plain English stats question"},
                "table_hint": {
                    "type": "string",
                    "description": "Optional hint such as batting, bowling, matches, or players",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the live web for recent or current information. "
            "Use only for current, recent, latest, today, now, or live questions. "
            "Maximum 2 calls per question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query":  {"type": "string", "description": "Short web query under 10 words"},
                "reason": {"type": "string", "description": "Why live web data is needed"},
            },
            "required": ["query", "reason"],
        },
    },
]

TOOL_DISPATCH = {
    "search_docs": search_docs,
    "query_data":  query_data,
    "web_search":  web_search,
}


# ---------------------------------------------------------------------------
# JSON repair utilities
# ---------------------------------------------------------------------------

def _repair_json(raw: str) -> str:
    """Add missing closing braces that Groq sometimes omits when truncating."""
    raw = raw.strip()
    open_braces  = raw.count("{")
    close_braces = raw.count("}")
    if open_braces > close_braces:
        raw += "}" * (open_braces - close_braces)
    return raw


def _parse_tool_args(raw: str) -> Dict[str, Any]:
    """Parse tool arguments JSON; attempt brace-repair before giving up."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        repaired = _repair_json(raw)
        try:
            result = json.loads(repaired)
            print(f"[WARN] Repaired malformed tool JSON: {repaired}")
            return result
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Cannot parse tool arguments even after repair: {raw!r}"
            ) from exc


# ---------------------------------------------------------------------------
# Safe LLM call — 3-attempt model ladder
# ---------------------------------------------------------------------------

def _is_recoverable_error(error_str: str) -> bool:
    return any(
        kw in error_str
        for kw in (
            "tool_use_failed",
            "Failed to call a function",
            "failed_generation",
            "model_decommissioned",
            "has been decommissioned",
        )
    )


def _make_groq_tools(tool_definitions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tool_definitions
    ]


def _safe_llm_call(
    client: GroqCompatClient,
    model: str,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    temperature: float = 0,
    max_tokens: int = MAX_COMPLETION_TOKENS,
) -> Any:
    """
    3-attempt model ladder for Groq tool-call failures.

    Attempt 1 — MODEL_PRIMARY  + tools
    Attempt 2 — MODEL_FALLBACK + tools   (different model, better JSON reliability)
    Attempt 3 — MODEL_NOTOOL,  no tools  (graceful degradation; answers from context)
    """
    # Use the underlying Groq chat API directly (not the compat .messages shim)
    groq_chat = client.chat.completions

    # Attempt 1
    try:
        return groq_chat.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )
    except Exception as exc:
        if not _is_recoverable_error(str(exc)):
            raise
        print(f"[WARN] Attempt 1 failed (model={model}): {str(exc)[:200]}")

    # Attempt 2
    try:
        return groq_chat.create(
            model=MODEL_FALLBACK,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )
    except Exception as exc:
        if not _is_recoverable_error(str(exc)):
            raise
        print(
            f"[WARN] Attempt 2 failed (model={MODEL_FALLBACK}): {str(exc)[:200]}\n"
            f"[WARN] Falling back to no-tools call (model={MODEL_NOTOOL})."
        )

    # Attempt 3 — no tools
    return groq_chat.create(
        model=MODEL_NOTOOL,
        messages=messages,
        temperature=temperature,
        max_completion_tokens=max_tokens,
    )


# ---------------------------------------------------------------------------
# Agent entry point
# ---------------------------------------------------------------------------

class CapExceededError(Exception):
    pass


def run_agent(user_question: str) -> Dict[str, Any]:
    tracer   = Tracer(user_question)
    telemetry = _init_telemetry()

    cached = load_cache(user_question)
    if cached:
        try:
            tracer.log_cache_hit()
        except Exception:
            pass
        return cached

    gate = gatekeeper_check(user_question)
    if gate["action"] == "direct_answer":
        result = _build_result(
            question=user_question, final_answer=gate["answer"], citations=[],
            status="direct_answer", steps_used=0,
            uncertainty="High confidence: no retrieval needed.",
            reflection=None, telemetry=_finalize_telemetry(telemetry),
            trace_path=_safe_trace_finalize(
                tracer=tracer, answer=gate["answer"], citations=[],
                status="direct_answer", steps_used=0,
            ),
        )
        save_cache(user_question, result)
        return result

    if gate["action"] == "refuse":
        result = _build_result(
            question=user_question, final_answer=gate["answer"], citations=[],
            status="refused", steps_used=0,
            uncertainty="Refused safely before retrieval.",
            reflection=None, telemetry=_finalize_telemetry(telemetry),
            trace_path=_safe_trace_finalize(
                tracer=tracer, answer=gate["answer"], citations=[],
                status="refused", steps_used=0,
            ),
        )
        save_cache(user_question, result)
        return result

    normalized = normalize_query(user_question)
    if normalized.get("scope_trap"):
        result = _build_result(
            question=user_question, final_answer=normalized["scope_trap_response"],
            citations=[], status="scope_clarification", steps_used=0,
            uncertainty="Question too broad; clarification requested.",
            reflection=None, telemetry=_finalize_telemetry(telemetry),
            trace_path=_safe_trace_finalize(
                tracer=tracer, answer=normalized["scope_trap_response"],
                citations=[], status="scope_clarification", steps_used=0,
            ),
        )
        save_cache(user_question, result)
        return result

    goals = decompose_goals(normalized)
    plan  = _build_plan(normalized, goals)

    try:
        tracer.log_plan(plan)
    except Exception:
        pass

    memory   = EvidenceMemory()
    messages = _initial_messages(normalized["question"], plan)

    loop_turns = 0
    tool_calls = 0
    web_calls  = 0

    while loop_turns < MAX_LOOP_TURNS:
        loop_turns += 1

        available_tools = (
            TOOL_DEFINITIONS
            if web_calls < MAX_WEB_CALLS
            else [t for t in TOOL_DEFINITIONS if t["name"] != "web_search"]
        )

        groq_tools = _make_groq_tools(available_tools)

        response = _safe_llm_call(
            client=get_client(),
            model=MODEL_PRIMARY,
            messages=messages,
            tools=groq_tools,
        )

        assistant_message = response.choices[0].message

        if not getattr(assistant_message, "tool_calls", None):
            break

        tool_call   = assistant_message.tool_calls[0]
        tool_name   = tool_call.function.name
        tool_use_id = tool_call.id

        raw_args = tool_call.function.arguments or "{}"
        try:
            tool_input = _parse_tool_args(raw_args)
        except ValueError as parse_err:
            print(f"[ERROR] {parse_err}")
            messages = _add_tool_result(
                messages=messages, assistant_message=assistant_message,
                tool_use_id=tool_use_id, result={"error": str(parse_err)},
            )
            continue

        if normalized.get("zone") == 3 and web_calls == 0 and tool_name != "web_search":
            try:
                tracer.log_zone_override(tool_name)
            except Exception:
                pass
            messages = _add_tool_result(
                messages=messages, assistant_message=assistant_message,
                tool_use_id=tool_use_id,
                result={"warning": "Current/live query detected. Call web_search first."},
            )
            continue

        if tool_name == "web_search" and web_calls >= MAX_WEB_CALLS:
            messages = _add_tool_result(
                messages=messages, assistant_message=assistant_message,
                tool_use_id=tool_use_id,
                result={"warning": "Maximum web_search limit reached for this question."},
            )
            continue

        call_hash = _hash_tool_call(tool_name, tool_input)
        if memory.is_duplicate(call_hash):
            try:
                tracer.log_duplicate_blocked(tool_name, tool_input)
            except Exception:
                pass
            messages = _add_tool_result(
                messages=messages, assistant_message=assistant_message,
                tool_use_id=tool_use_id,
                result={"warning": "Duplicate tool call blocked. Try a different tool or query."},
            )
            continue

        if tool_calls >= MAX_TOOL_CALLS:
            break

        start   = time.time()
        success = True
        result  = None

        try:
            result = TOOL_DISPATCH[tool_name](**tool_input)
        except Exception as first_error:
            try:
                tracer.log_tool_error(tool_name, tool_input, str(first_error))
            except Exception:
                pass
            try:
                result = TOOL_DISPATCH[tool_name](**tool_input)
            except Exception as second_error:
                success = False
                result  = {"error": str(second_error), "tool": tool_name}

        latency_ms = int((time.time() - start) * 1000)

        tool_calls += 1
        if tool_name == "web_search":
            web_calls += 1

        memory.add(tool_name, tool_input, result, call_hash)
        memory.mark_duplicate(call_hash)
        goals = update_goals(goals, tool_name, result)

        _update_telemetry(telemetry, tool_name, latency_ms)

        try:
            tracer.log_step(tool_calls, tool_name, tool_input, result, latency_ms, success)
        except Exception:
            pass

        messages = _add_tool_result(
            messages=messages, assistant_message=assistant_message,
            tool_use_id=tool_use_id, result=result,
        )

        if is_sufficient(goals, normalized, memory):
            break

    open_goals = [g for g in goals if g.get("status") == "OPEN"]

    if tool_calls >= MAX_TOOL_CALLS and open_goals:
        final_answer = (
            f"I could not fully answer the question within the {MAX_TOOL_CALLS}-tool-call limit. "
            f"Unresolved goals: {'; '.join(g.get('description', 'unknown goal') for g in open_goals)}."
        )
        final_result = _build_result(
            question=user_question, final_answer=final_answer, citations=[],
            status="cap_exceeded", steps_used=tool_calls,
            uncertainty="Low confidence: hard cap reached before resolving all goals.",
            reflection=None, telemetry=_finalize_telemetry(telemetry),
            trace_path=_safe_trace_finalize(
                tracer=tracer, answer=final_answer, citations=[],
                status="cap_exceeded", steps_used=tool_calls,
            ),
        )
        save_cache(user_question, final_result)
        return final_result

    # ── Compose final answer (layer files may use client.messages.create) ──
    client = get_client()   # GroqCompatClient — supports both API styles

    answer_payload        = compose_answer(normalized["question"], goals, memory, client)
    answer_text, citations = _normalize_answer_payload(answer_payload)

    bound_payload          = bind_citations(answer_text, memory)
    bound_text, bound_citations = _normalize_answer_payload(bound_payload)

    if bound_citations:
        citations = bound_citations

    reflection_result = None
    try:
        reflected_payload, reflection_result = reflect(
            normalized["question"],
            {"final_answer": bound_text, "citations": citations},
            memory, goals, tool_calls, MAX_TOOL_CALLS, client,
        )
        reflected_text, reflected_citations = _normalize_answer_payload(reflected_payload)
        if reflected_text:
            bound_text = reflected_text
        if reflected_citations:
            citations = reflected_citations
    except Exception:
        reflection_result = {
            "passed": False,
            "issue": "Reflection failed; using pre-reflection answer.",
        }

    try:
        uncertainty = build_uncertainty_statement(memory, goals, normalized["zone"])
    except Exception:
        uncertainty = "Moderate confidence: answer grounded in retrieved tool outputs."

    telemetry = _finalize_telemetry(telemetry)

    final_result = _build_result(
        question=user_question, final_answer=bound_text, citations=citations,
        status="answered", steps_used=tool_calls, uncertainty=uncertainty,
        reflection=reflection_result, telemetry=telemetry,
        trace_path=_safe_trace_finalize(
            tracer=tracer, answer=bound_text, citations=citations,
            status="answered", steps_used=tool_calls,
            uncertainty=uncertainty, reflection=reflection_result,
        ),
    )

    save_cache(user_question, final_result)
    return final_result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_plan(normalized: Dict[str, Any], goals: List[Dict[str, Any]]) -> str:
    tool_types: List[str] = []
    for goal in goals:
        tool_type = goal.get("tool_type")
        if tool_type and tool_type not in tool_types:
            tool_types.append(tool_type)

    mapped_tools: List[str] = []
    for item in tool_types:
        if item == "statistical":
            mapped_tools.append("query_data")
        elif item == "narrative":
            mapped_tools.append("search_docs")
        elif item == "current":
            mapped_tools.append("web_search")
        else:
            mapped_tools.append(item)

    goal_text = "; ".join(g.get("description", "") for g in goals) or "answer the question"
    zone_note = (
        "Use web_search first because the query appears current/live."
        if normalized.get("zone") == 3
        else "Use corpus tools first because the query appears historical/corpus-bound."
    )
    return (
        f"Plan: Use {', '.join(mapped_tools) if mapped_tools else 'available tools'} "
        f"to resolve these goals: {goal_text}. {zone_note}"
    )


def _initial_messages(question: str, plan: str) -> List[Dict[str, Any]]:
    return [
        {
            "role": "system",
            "content": (
                "You are an IPL agent. Use tools when needed. "
                "Do not answer from memory. "
                "Every factual claim must come from tool outputs."
            ),
        },
        {
            "role": "user",
            "content": f"Question: {question}\n\nPlan: {plan}",
        },
    ]


def _add_tool_result(
    messages: List[Dict[str, Any]],
    assistant_message: Any,
    tool_use_id: str,
    result: Any,
) -> List[Dict[str, Any]]:
    messages.append(
        {
            "role": "assistant",
            "content": assistant_message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in (assistant_message.tool_calls or [])
            ],
        }
    )
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_use_id,
            "content": json.dumps(result, ensure_ascii=False, default=str),
        }
    )
    return messages


def _hash_tool_call(tool_name: str, tool_input: Dict[str, Any]) -> str:
    raw = f"{tool_name}:{json.dumps(tool_input, sort_keys=True, default=str)}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _normalize_answer_payload(payload: Any) -> Tuple[str, List[str]]:
    if isinstance(payload, str):
        return payload, []
    if isinstance(payload, dict):
        text      = payload.get("final_answer") or payload.get("answer") or payload.get("text") or ""
        citations = payload.get("citations", [])
        if not isinstance(citations, list):
            citations = [str(citations)]
        return str(text), [str(c) for c in citations]
    return str(payload), []


def _build_result(
    question: str, final_answer: str, citations: List[str],
    status: str, steps_used: int, uncertainty: str,
    reflection: Any, telemetry: Dict[str, Any], trace_path: Any,
) -> Dict[str, Any]:
    return {
        "question":     question,
        "final_answer": final_answer,
        "citations":    citations,
        "status":       status,
        "steps_used":   steps_used,
        "uncertainty":  uncertainty,
        "reflection":   reflection,
        "telemetry":    telemetry,
        "trace_path":   trace_path,
    }


def _init_telemetry() -> Dict[str, Dict[str, Any]]:
    return {
        "search_docs": {"calls": 0, "latencies_ms": [], "avg_latency_ms": 0},
        "query_data":  {"calls": 0, "latencies_ms": [], "avg_latency_ms": 0},
        "web_search":  {"calls": 0, "latencies_ms": [], "avg_latency_ms": 0},
    }


def _update_telemetry(telemetry: Dict[str, Any], tool_name: str, latency_ms: int) -> None:
    if tool_name not in telemetry:
        telemetry[tool_name] = {"calls": 0, "latencies_ms": [], "avg_latency_ms": 0}
    telemetry[tool_name]["calls"] += 1
    telemetry[tool_name]["latencies_ms"].append(latency_ms)


def _finalize_telemetry(telemetry: Dict[str, Any]) -> Dict[str, Any]:
    for _, stats in telemetry.items():
        latencies = stats.get("latencies_ms", [])
        stats["avg_latency_ms"] = int(sum(latencies) / len(latencies)) if latencies else 0
    return telemetry


def _safe_trace_finalize(
    tracer: Any, answer: str, citations: List[str],
    status: str, steps_used: int,
    uncertainty: str = None, reflection: Any = None,
) -> Any:
    try:
        return tracer.finalize(
            answer=answer, citations=citations, status=status,
            steps_used=steps_used, uncertainty=uncertainty, reflection=reflection,
        )
    except TypeError:
        try:
            return tracer.finalize(answer, citations, status, steps_used=steps_used)
        except Exception:
            return None
    except Exception:
        return None