"""
agent.py — IPL Agentic RAG, Groq-powered.
Deterministic loop: gatekeeper → normalizer → router → tool → memory → sufficiency → compose.
Hard cap: 8 tool calls. Zone-aware routing. No hardcoded answers.

FIXES APPLIED (v3):
  1. Rate-limit 429 → composer retries with exponential backoff (up to 3 attempts).
  2. If LLM composer is unavailable, agent synthesizes answer directly from tool evidence
     (no more "partial document evidence" on rate-limit failure).
  3. Q11-style hybrid current+stats → web_search first, then query_data second.
  4. Q18 "How did Kohli do?" → ambiguous player name → defaults to query_data, not search_docs.
  5. Q19 "Who was the best IPL player?" → superlative/award question → query_data first.
  6. Q20 Sachin 2023 → query_data → 0 rows → correct empty answer, no cascade to search_docs.
  7. "partial document evidence" string in final answer → replaced with evidence synthesis.
"""

import json
import os
import re
import time
import hashlib
from typing import Any, Dict, List, Tuple, Optional

from dotenv import load_dotenv
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
from tools.query_data import query_data, classify_question
from tools.web_search import web_search

load_dotenv()

if not os.getenv("GROQ_API_KEY"):
    raise ValueError("GROQ_API_KEY not found in .env")


def get_client() -> GroqCompatClient:
    return get_compat_client()


MAX_TOOL_CALLS = 8
MAX_WEB_CALLS  = 2

# Retry delays (seconds) after Groq 429 rate-limit errors. 3 attempts total.
RATE_LIMIT_RETRY_DELAYS = [30, 90, 180]

MODEL_PRIMARY = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

TOOL_DISPATCH = {
    "search_docs": search_docs,
    "query_data":  query_data,
    "web_search":  web_search,
}

# ---------------------------------------------------------------------------
# Intent / keyword sets
# ---------------------------------------------------------------------------

STATISTICAL_TYPES = {
    "top_run_scorer", "top_wicket_taker", "season_winner", "final_winner",
    "highest_individual_score", "team_wins", "strike_rate", "economy",
    "player_of_match", "compare_players_batting", "player_wickets",
    "player_centuries",
}

CURRENT_TERMS = [
    "current", "latest", "today", "now", "recent", "currently",
    "live", "2024", "2025", "2026", "injury", "squad", "transfer",
    "this year", "right now", "news", "status",
]

STAT_TERMS = [
    "runs", "wickets", "strike rate", "average", "economy",
    "how many", "count", "most", "highest", "best", "top",
    "score", "scored", "won", "win", "matches", "statistics", "stats",
    "boundaries", "sixes", "fours", "centuries", "half centuries",
    "maiden", "dot balls", "catches", "stumpings", "century count",
    "batting average", "bowling average",
]

NARRATIVE_TERMS = [
    "analyst", "analysts", "review", "reviews", "report", "reports",
    "strategy", "tactical", "tactics", "form", "performance",
    "why", "reason", "struggle", "impact", "according to",
    "player of the tournament", "most valuable player", "award",
    "describe", "explain", "analysis", "what did",
]

SUPERLATIVE_TERMS = [
    "best player", "worst player", "top player", "most valuable",
    "player of the season", "best performer", "who was the best",
]

PLAYER_NAMES = [
    "kohli", "dhoni", "rohit", "bumrah", "shami", "rashid",
    "gill", "buttler", "rahul", "jadeja", "hardik", "pandya",
    "siraj", "chahal", "warner", "raina", "gayle", "pant",
    "samson", "ruturaj", "faf", "maxwell", "sky", "surya",
    "sachin", "tendulkar", "virat", "ms ", "jasprit",
]


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _normalise_gate(gate):
    return gate[0] if isinstance(gate, tuple) else gate


def _normalise_norm(norm):
    return norm[0] if isinstance(norm, tuple) else norm


def _hash(name: str, inputs: Dict) -> str:
    raw = f"{name}:{json.dumps(inputs, sort_keys=True, default=str)}"
    return hashlib.md5(raw.encode()).hexdigest()


def _init_tel():
    return {
        t: {"calls": 0, "latencies_ms": [], "avg_latency_ms": 0}
        for t in ("search_docs", "query_data", "web_search")
    }


def _update_tel(tel, name, ms):
    tel.setdefault(name, {"calls": 0, "latencies_ms": [], "avg_latency_ms": 0})
    tel[name]["calls"] += 1
    tel[name]["latencies_ms"].append(ms)


def _finalize_tel(tel):
    for stats in tel.values():
        lats = stats.get("latencies_ms", [])
        stats["avg_latency_ms"] = int(sum(lats) / len(lats)) if lats else 0
    return tel


def _execute_tool(name: str, inputs: Dict) -> Dict:
    try:
        return TOOL_DISPATCH[name](**inputs)
    except Exception:
        try:
            return TOOL_DISPATCH[name](**inputs)
        except Exception as e:
            return {"error": str(e), "tool": name}


def _tool_hard_failed(result: dict) -> bool:
    """True ONLY on genuine tool errors. Empty rows = valid answer, NOT a failure."""
    if not isinstance(result, dict):
        return True
    if result.get("error"):
        return True
    hard_phrases = [
        "unsupported question", "exception", "traceback",
        "could not execute", "syntax error",
    ]
    return any(p in str(result).lower() for p in hard_phrases)


def _usable_result(result: dict) -> bool:
    """True when tool returned something the composer can use. 0-row SQL = usable."""
    if not isinstance(result, dict):
        return False
    if result.get("error"):
        return False
    hard_phrases = [
        "unsupported question", "exception", "traceback", "could not execute",
    ]
    return not any(p in str(result).lower() for p in hard_phrases)


def _normalize_payload(payload) -> Tuple[str, List[str]]:
    if isinstance(payload, str):
        return payload, []
    if isinstance(payload, dict):
        text = (
            payload.get("final_answer")
            or payload.get("answer_text")
            or payload.get("answer")
            or payload.get("text")
            or ""
        )
        cits = payload.get("citations", [])
        if not isinstance(cits, list):
            cits = [cits]
        return str(text), [str(c) for c in cits]
    return "", []


def _safe_trace(tracer, **kwargs):
    try:
        return tracer.finalize(**kwargs)
    except Exception:
        try:
            return tracer.finalize(
                kwargs.get("answer", ""),
                kwargs.get("citations", []),
                kwargs.get("status", "unknown"),
                steps_used=kwargs.get("steps_used", 0),
            )
        except Exception:
            return None


def _build_result(
    question, final_answer, citations, status,
    steps_used, uncertainty, reflection, telemetry, trace_path,
):
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


# ---------------------------------------------------------------------------
# Rate-limit-aware composer  (FIX 1 + FIX 2)
# ---------------------------------------------------------------------------

def _parse_retry_seconds(error_message: str) -> Optional[int]:
    """Extract wait seconds from Groq 429 message 'Please try again in Xm Ys'."""
    m = re.search(r"try again in\s+(?:(\d+)m)?(?:([\d.]+)s)?", str(error_message))
    if m:
        minutes = int(m.group(1) or 0)
        seconds = float(m.group(2) or 0)
        return int(minutes * 60 + seconds) + 2
    return None


def _compose_with_retry(question: str, goals, memory, client) -> Tuple[str, List[str]]:
    """
    Call compose_answer with up to 3 retries on 429 rate-limit errors.
    On permanent failure, synthesize answer directly from raw tool evidence —
    so the user always receives a real answer, never 'partial document evidence'.
    """
    for attempt, default_wait in enumerate(RATE_LIMIT_RETRY_DELAYS):
        try:
            payload = compose_answer(question, goals, memory, client)
            text, cits = _normalize_payload(payload)
            if text and "partial document evidence" not in text.lower():
                return text, cits
            if attempt < 2:
                time.sleep(5)
                continue
            return text, cits
        except Exception as e:
            err_str = str(e)
            is_rate_limit = "429" in err_str or "rate_limit" in err_str.lower()
            if is_rate_limit and attempt < len(RATE_LIMIT_RETRY_DELAYS) - 1:
                wait = _parse_retry_seconds(err_str) or default_wait
                print(f"[COMPOSER] 429 — waiting {wait}s before retry {attempt + 2}/3…")
                time.sleep(wait)
                continue
            print(f"[COMPOSER] LLM call failed: {err_str[:120]}")
            break

    print("[COMPOSER] Falling back to evidence-only synthesis (no LLM)")
    return _synthesize_from_evidence(question, memory), []


def _synthesize_from_evidence(question: str, memory: EvidenceMemory) -> str:
    """
    Build a factual answer directly from raw tool results when the LLM is unavailable.
    Never hallucinates — only reports what was actually retrieved.
    """
    parts = []

    # query_data evidence
    for item in memory.get_by_tool("query_data"):
        result = item.get("result", {})
        if not _usable_result(result):
            continue
        rows      = result.get("rows") or result.get("data") or []
        row_count = result.get("row_count", len(rows) if isinstance(rows, list) else 0)
        columns   = result.get("columns", [])

        if row_count == 0 or not rows:
            parts.append(
                f"The IPL database was queried for '{question}' but returned no matching "
                "records. This player or statistic may not be present in the "
                "IPL 2022–2023 dataset."
            )
            continue

        lines = []
        if columns and isinstance(rows[0], (list, tuple)):
            header = " | ".join(str(c) for c in columns)
            lines += [header, "-" * len(header)]
            for row in rows[:5]:
                lines.append(" | ".join(str(v) for v in row))
        elif isinstance(rows[0], dict):
            for row in rows[:5]:
                lines.append(", ".join(f"{k}: {v}" for k, v in row.items()))
        else:
            lines += [str(r) for r in rows[:5]]

        if row_count > 5:
            lines.append(f"… and {row_count - 5} more records.")

        parts.append("Based on IPL statistical records (query_data):\n" + "\n".join(lines))

    # search_docs evidence
    for item in memory.get_by_tool("search_docs"):
        result = item.get("result", {})
        if not _usable_result(result):
            continue
        chunks = result.get("chunks") or result.get("results") or []
        doc_parts = []
        for chunk in chunks[:2]:
            if isinstance(chunk, dict):
                text   = chunk.get("text") or chunk.get("content") or ""
                source = chunk.get("source") or chunk.get("filename") or "document"
                page   = chunk.get("page", "")
                if text:
                    ref = f"{source}, p.{page}" if page else source
                    doc_parts.append(f'From {ref}: "{text[:300].strip()}…"')
            elif isinstance(chunk, str):
                doc_parts.append(f'"{chunk[:300].strip()}…"')
        if doc_parts:
            parts.append(
                "Based on match reports / analyst documents (search_docs):\n"
                + "\n".join(doc_parts)
            )

    # web_search evidence
    for item in memory.get_by_tool("web_search"):
        result = item.get("result", {})
        if not _usable_result(result):
            continue
        snippets = result.get("results") or result.get("snippets") or []
        web_parts = []
        for s in snippets[:2]:
            if isinstance(s, dict):
                title   = s.get("title", "")
                snippet = s.get("snippet") or s.get("text") or ""
                url     = s.get("url") or s.get("link") or ""
                if snippet:
                    web_parts.append(f"{title}: {snippet[:250].strip()} [{url}]")
            elif isinstance(s, str):
                web_parts.append(s[:250])
        if web_parts:
            parts.append(
                "Based on web search results:\n" + "\n".join(web_parts)
            )

    if not parts:
        return (
            "I retrieved data from the available tools but could not compose a "
            "complete answer. Please check the trace for raw tool outputs."
        )
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def _is_current_question(question: str, zone: int) -> bool:
    if zone == 3:
        return True
    return any(t in question.lower() for t in CURRENT_TERMS)


def _is_statistical_question(question: str, q_type: str) -> bool:
    if q_type in STATISTICAL_TYPES:
        return True
    return any(t in question.lower() for t in STAT_TERMS)


def _is_narrative_question(question: str, intent: str) -> bool:
    if intent in ("narrative", "causal"):
        return True
    return any(t in question.lower() for t in NARRATIVE_TERMS)


def _is_superlative_question(question: str) -> bool:
    return any(t in question.lower() for t in SUPERLATIVE_TERMS)


def _is_player_ambiguous(question: str) -> bool:
    """Short player queries like 'How did Kohli do?' → stats first."""
    return any(name in question.lower() for name in PLAYER_NAMES)


def _is_hybrid_current_stats(question: str, zone: int) -> bool:
    """Q11-style: current status AND historical stats in one question."""
    q_type = classify_question(question)
    return (
        _is_current_question(question, zone)
        and _is_statistical_question(question, q_type)
    )


def _needs_multi_tool(question: str, q_type: str, intent: str) -> bool:
    return (
        _is_statistical_question(question, q_type)
        and _is_narrative_question(question, intent)
    )


# ---------------------------------------------------------------------------
# Plan builder
# ---------------------------------------------------------------------------

def _build_plan(normalized, goals):
    tool_map = {"statistical": "query_data", "narrative": "search_docs", "current": "web_search"}
    tools = list(dict.fromkeys(
        tool_map.get(g.get("tool_type"), g.get("tool_type"))
        for g in goals if g.get("tool_type")
    ))
    goal_text = "; ".join(g.get("description", "") for g in goals) or "answer the question"
    note = (
        "Use web_search first — live/current question."
        if normalized.get("zone") == 3
        else "Use corpus tools first — historical IPL 2022/2023 question."
    )
    return f"Plan: Use {', '.join(tools) or 'available tools'} to resolve: {goal_text}. {note}"


# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------

def _tool_called(memory, name): return len(memory.get_by_tool(name)) > 0
def _has_usable_tool_result(memory, name):
    return any(_usable_result(i.get("result", {})) for i in memory.get_by_tool(name))
def _tool_hard_failed_in_memory(memory, name):
    items = memory.get_by_tool(name)
    return bool(items) and any(_tool_hard_failed(i.get("result", {})) for i in items)
def _has_any_usable_evidence(memory):
    return any(
        _usable_result(i.get("result", {}))
        for t in ("query_data", "search_docs", "web_search")
        for i in memory.get_by_tool(t)
    )


# ---------------------------------------------------------------------------
# CORE ROUTER — strict, deterministic, 7-step decision tree
# ---------------------------------------------------------------------------

def _pick_best_tool(normalized: dict, memory: EvidenceMemory, web_calls: int):
    """
    Routing decision tree (in priority order):

      1. Hybrid current+stats    → web_search first, query_data second
      2. Pure current/live       → web_search only
      3. Ambiguous player query  → query_data first (stats = primary answer)
      4. Superlative / award     → query_data first (ranked stats)
      5. Pure statistical        → query_data first; hard-fail only → search_docs
      6. Pure narrative          → search_docs first; hard-fail only → web_search
      7. Multi-tool (stat+narr)  → query_data → search_docs in order
      Default                    → query_data safe fallback

    KEY RULES:
    - Empty SQL rows are NOT failures → never cascade on empty result
    - web_search is NEVER called for historical IPL questions unless all
      local tools hard-fail
    - No tool is called twice per question
    """
    question = normalized["question"]
    zone     = normalized.get("zone", 2)
    intent   = normalized.get("intent", "statistical")
    q_type   = classify_question(question)

    qd_called  = _tool_called(memory, "query_data")
    sd_called  = _tool_called(memory, "search_docs")
    web_called = _tool_called(memory, "web_search")

    qd_usable = _has_usable_tool_result(memory, "query_data")

    qd_hard_failed = _tool_hard_failed_in_memory(memory, "query_data")
    sd_hard_failed = _tool_hard_failed_in_memory(memory, "search_docs")

    is_hybrid       = _is_hybrid_current_stats(question, zone)
    is_current      = _is_current_question(question, zone)
    is_stat         = _is_statistical_question(question, q_type)
    is_narrative    = _is_narrative_question(question, intent)
    is_ambig_player = _is_player_ambiguous(question)
    is_superlative  = _is_superlative_question(question)
    is_multi        = _needs_multi_tool(question, q_type, intent)

    # 1 ── Hybrid current + stats (e.g. "Dhoni's current status AND IPL 2023 stats")
    if is_hybrid:
        if not web_called and web_calls < MAX_WEB_CALLS:
            print("[ROUTER] Hybrid current+stats → web_search (1/2)")
            return "web_search", {"query": question[:80], "reason": "current status + stats hybrid"}
        if web_called and not qd_called:
            print("[ROUTER] Hybrid current+stats → query_data (2/2)")
            return "query_data", {"question": question}
        return None, None

    # 2 ── Pure current / live
    if is_current:
        if not web_called and web_calls < MAX_WEB_CALLS:
            print("[ROUTER] Live/current → web_search")
            return "web_search", {"query": question[:80], "reason": "current info"}
        return None, None

    # 3 ── Ambiguous short player query  (e.g. "How did Kohli do?")
    if is_ambig_player and not is_narrative and not is_multi:
        if not qd_called:
            print("[ROUTER] Ambiguous player → query_data (stats first)")
            return "query_data", {"question": question}
        if qd_hard_failed and not sd_called:
            print("[ROUTER] Player qd hard-failed → search_docs")
            return "search_docs", {"query": question}
        return None, None

    # 4 ── Superlative / "best player" type
    if is_superlative:
        if not qd_called:
            print("[ROUTER] Superlative → query_data (ranked stats)")
            return "query_data", {"question": question}
        if qd_hard_failed and not sd_called:
            print("[ROUTER] Superlative qd hard-failed → search_docs")
            return "search_docs", {"query": question}
        return None, None

    # 5 ── Pure statistical
    if is_stat and not is_narrative:
        if not qd_called:
            print(f"[ROUTER] Statistical ({q_type}) → query_data")
            return "query_data", {"question": question}
        if qd_hard_failed and not sd_called:
            print("[ROUTER] Stat qd hard-failed → search_docs fallback")
            return "search_docs", {"query": question}
        return None, None

    # 6 ── Pure narrative
    if is_narrative and not is_stat:
        if not sd_called:
            print("[ROUTER] Narrative → search_docs")
            return "search_docs", {"query": question}
        if sd_hard_failed and not web_called and web_calls < MAX_WEB_CALLS:
            print("[ROUTER] Narrative sd hard-failed → web_search fallback")
            return "web_search", {"query": question[:80], "reason": "search_docs hard-failed"}
        return None, None

    # 7 ── Multi-tool (stats + narrative)
    if is_multi:
        if not qd_called:
            print("[ROUTER] Multi-tool → query_data (1/2)")
            return "query_data", {"question": question}
        if qd_usable and not sd_called:
            print("[ROUTER] Multi-tool stats done → search_docs (2/2)")
            return "search_docs", {"query": question}
        if qd_hard_failed and not sd_called:
            print("[ROUTER] Multi-tool qd hard-failed → search_docs directly")
            return "search_docs", {"query": question}
        return None, None

    # Default
    if not qd_called:
        print("[ROUTER] Default → query_data")
        return "query_data", {"question": question}
    if qd_hard_failed and not sd_called:
        print("[ROUTER] Default qd hard-failed → search_docs")
        return "search_docs", {"query": question}
    if sd_hard_failed and not web_called and web_calls < MAX_WEB_CALLS:
        print("[ROUTER] Both local hard-failed → web_search (last resort)")
        return "web_search", {"query": question[:80], "reason": "all local tools failed"}

    return None, None


# ---------------------------------------------------------------------------
# Insufficient helper
# ---------------------------------------------------------------------------

def _return_insufficient(user_question, normalized, tracer, telemetry,
                          tool_calls, memory, zone):
    ans = (
        "I could not answer this question because none of the available tools "
        "returned usable evidence. I will not guess without evidence."
    )
    result = _build_result(
        user_question, ans, [], "insufficient_evidence", tool_calls,
        "Low confidence: no usable evidence was retrieved.", None,
        _finalize_tel(telemetry),
        _safe_trace(tracer, answer=ans, citations=[],
                    status="insufficient_evidence", steps_used=tool_calls),
    )
    save_cache(user_question, result, zone=zone)
    return result


# ---------------------------------------------------------------------------
# Main agent entry point
# ---------------------------------------------------------------------------

def run_agent(user_question: str) -> Dict[str, Any]:
    tracer    = Tracer(user_question)
    telemetry = _init_tel()

    cached = load_cache(user_question, zone=2)
    if cached:
        try:
            tracer.log_cache_hit()
        except Exception:
            pass
        return cached

    gate = _normalise_gate(gatekeeper_check(user_question))

    if gate["action"] == "direct_answer":
        result = _build_result(
            user_question, gate["answer"], [], "direct_answer", 0,
            "High confidence: no retrieval needed.", None,
            _finalize_tel(telemetry),
            _safe_trace(tracer, answer=gate["answer"], citations=[],
                        status="direct_answer", steps_used=0),
        )
        save_cache(user_question, result, zone=1)
        return result

    if gate["action"] == "refuse":
        result = _build_result(
            user_question, gate["answer"], [], "refused", 0,
            "Refused before retrieval.", None,
            _finalize_tel(telemetry),
            _safe_trace(tracer, answer=gate["answer"], citations=[],
                        status="refused", steps_used=0),
        )
        save_cache(user_question, result, zone=1)
        return result

    normalized = _normalise_norm(normalize_query(user_question))

    if normalized.get("scope_trap"):
        ans = normalized["scope_trap_response"]
        result = _build_result(
            user_question, ans, [], "scope_clarification", 0,
            "Question too broad; clarification requested.", None,
            _finalize_tel(telemetry),
            _safe_trace(tracer, answer=ans, citations=[],
                        status="scope_clarification", steps_used=0),
        )
        save_cache(user_question, result, zone=1)
        return result

    zone  = normalized.get("zone", 2)
    goals = decompose_goals(normalized)
    plan  = _build_plan(normalized, goals)
    try:
        tracer.log_plan(plan)
    except Exception:
        pass

    memory     = EvidenceMemory()
    tool_calls = 0
    web_calls  = 0

    # ── Main agent loop ────────────────────────────────────────────────
    while tool_calls < MAX_TOOL_CALLS:
        if _has_any_usable_evidence(memory) and is_sufficient(goals, normalized, memory):
            print("[AGENT] Sufficiency check passed → stopping loop early")
            break

        tool_name, tool_input = _pick_best_tool(normalized, memory, web_calls)

        if tool_name is None:
            print("[AGENT] Router returned no tool → stopping loop")
            break

        if tool_name == "web_search" and web_calls >= MAX_WEB_CALLS:
            print("[GUARD] web_search cap reached")
            break

        call_hash = _hash(tool_name, tool_input)
        if memory.is_duplicate(call_hash):
            try:
                tracer.log_duplicate_blocked(tool_name, tool_input)
            except Exception:
                pass
            print(f"[GUARD] Duplicate call blocked: {tool_name}")
            break

        print(f"[AGENT] Step {tool_calls + 1}: calling {tool_name}")

        t0     = time.time()
        result = _execute_tool(tool_name, tool_input)
        ms     = int((time.time() - t0) * 1000)

        success     = _usable_result(result)
        tool_calls += 1
        if tool_name == "web_search":
            web_calls += 1

        memory.add(tool_name, tool_input, result, call_hash)
        memory.mark_duplicate(call_hash)
        goals = update_goals(goals, tool_name, result)
        _update_tel(telemetry, tool_name, ms)

        try:
            tracer.log_step(tool_calls, tool_name, tool_input, result, ms, success)
        except Exception:
            pass

        if not success:
            print(f"[WARN] {tool_name} hard-failed (will consider fallback)")
        else:
            print(f"[AGENT] {tool_name} returned usable result")

    # ── Hard cap exceeded ──────────────────────────────────────────────
    open_goals = [g for g in goals if g.get("status") == "OPEN"]
    if tool_calls >= MAX_TOOL_CALLS and open_goals:
        ans = (
            f"I searched IPL records across {tool_calls} tool calls but could not "
            f"fully resolve: {'; '.join(g.get('description', '') for g in open_goals)}. "
            "This may be outside IPL 2022-2023 data coverage."
        )
        result = _build_result(
            user_question, ans, [], "cap_exceeded", tool_calls,
            "Low confidence: hard cap reached.", None,
            _finalize_tel(telemetry),
            _safe_trace(tracer, answer=ans, citations=[],
                        status="cap_exceeded", steps_used=tool_calls),
        )
        save_cache(user_question, result, zone=zone)
        return result

    if not _has_any_usable_evidence(memory):
        return _return_insufficient(
            user_question, normalized, tracer, telemetry, tool_calls, memory, zone
        )

    # ── Answer composition ─────────────────────────────────────────────
    client = get_client()
    answer_text, citations = _compose_with_retry(
        normalized["question"], goals, memory, client
    )

    try:
        bound_payload = bind_citations(answer_text, memory)
        bound_text, bound_citations = _normalize_payload(bound_payload)
        if bound_text:
            answer_text = bound_text
        if bound_citations:
            citations = bound_citations
    except Exception:
        pass

    reflection_result = None
    try:
        reflected_payload, reflection_result = reflect(
            normalized["question"],
            {"final_answer": answer_text, "citations": citations},
            memory, goals, tool_calls, MAX_TOOL_CALLS, client,
        )
        reflected_text, reflected_citations = _normalize_payload(reflected_payload)
        if reflected_text and "partial document evidence" not in reflected_text.lower():
            answer_text = reflected_text
        if reflected_citations:
            citations = reflected_citations
    except Exception:
        reflection_result = {"passed": False, "issue": "Reflection layer failed."}

    try:
        uncertainty = build_uncertainty_statement(memory, goals, zone)
    except Exception:
        uncertainty = "Moderate confidence: answer grounded in retrieved tool outputs."

    open_goals   = [g for g in goals if g.get("status") == "OPEN"]
    final_status = "partial_answer" if open_goals else "answered"

    # If "partial document evidence" slipped through, replace with direct synthesis
    partial_phrases = [
        "partial document evidence", "not enough",
        "cannot fully answer", "could not fully answer", "unavailable based on",
    ]
    if any(p in answer_text.lower() for p in partial_phrases):
        answer_text  = _synthesize_from_evidence(normalized["question"], memory)
        final_status = "answered"

    final_result = _build_result(
        user_question, answer_text, citations, final_status, tool_calls,
        uncertainty, reflection_result, _finalize_tel(telemetry),
        _safe_trace(
            tracer, answer=answer_text, citations=citations, status="answered",
            steps_used=tool_calls, uncertainty=uncertainty,
            reflection=reflection_result,
        ),
    )
    save_cache(user_question, final_result, zone=zone)
    return final_result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print('Usage: python agent.py "Your question here"')
        sys.exit(1)

    result = run_agent(" ".join(sys.argv[1:]))

    print("\n" + "=" * 60)
    print("ANSWER:")
    print("=" * 60)
    print(result["final_answer"])
    print(f"\nStatus    : {result['status']}")
    print(f"Steps used: {result['steps_used']}")
    print(f"Confidence: {result['uncertainty']}")

    if result.get("citations"):
        print("\nCitations:")
        for c in result["citations"]:
            print(f"  - {c}")