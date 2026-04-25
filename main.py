"""
main.py — IPL Agentic RAG CLI entry point.

Usage:
    python main.py "Who scored the most runs in IPL 2023?"
    python main.py --eval
    python main.py --eval --fresh          # clears cache before eval
    python main.py --clear-cache
    python main.py --test                  # quick 5-question smoke test
"""

import json
import sys
import time
from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _print_result(result: dict, question: str) -> None:
    print(f"\nQuestion  : {question}")
    print("-" * 70)
    print(f"Answer    :\n{result['final_answer']}")

    if result.get("citations"):
        print("\nCitations :")
        for c in result["citations"]:
            print(f"  - {c}")

    print(f"\nStatus    : {result['status']}")
    print(f"Steps     : {result['steps_used']}")

    if result.get("uncertainty"):
        print(f"Confidence: {result['uncertainty']}")

    refl = result.get("reflection")
    if isinstance(refl, dict):
        status = "PASSED" if refl.get("passed") else "FAILED"
        issue  = refl.get("issue", "")
        print(f"Reflection: {status}" + (f" — {issue}" if issue else ""))

    tel = result.get("telemetry", {})
    if any(s.get("calls", 0) > 0 for s in tel.values()):
        print("\nTelemetry :")
        for tool, stats in tel.items():
            if stats.get("calls", 0) > 0:
                print(f"  {tool}: {stats['calls']} call(s), avg {stats['avg_latency_ms']} ms")

    tp = result.get("trace_path")
    if tp:
        print(f"Trace     : {tp}")


# ── Single question ───────────────────────────────────────────────────────────

def run_single(question: str) -> None:
    from agent import run_agent
    result = run_agent(question)
    _print_result(result, question)
    print()


# ── Full eval ─────────────────────────────────────────────────────────────────

def run_eval(fresh: bool = False) -> None:
    from agent import run_agent

    if fresh:
        from utils.cache import clear_cache
        clear_cache()
        print("[INFO] Cache cleared before eval.")

    eval_path = Path("eval/questions.json")
    if not eval_path.exists():
        print("ERROR: eval/questions.json not found.")
        return

    with eval_path.open(encoding="utf-8") as f:
        questions = json.load(f)

    if not isinstance(questions, list) or not questions:
        print("ERROR: eval/questions.json must be a non-empty list.")
        return

    results   = []
    total     = len(questions)
    print(f"\nRunning evaluation — {total} questions")
    print("=" * 70)

    for idx, item in enumerate(questions, 1):
        question       = (item.get("question", "") if isinstance(item, dict) else item).strip()
        category       = item.get("category", "unknown") if isinstance(item, dict) else "unknown"
        expected_tools = item.get("expected_tools", []) if isinstance(item, dict) else []
        expected_beh   = item.get("expected_behavior", "") if isinstance(item, dict) else ""

        if not question:
            print(f"[{idx}] Skipping empty entry.")
            continue

        print(f"\n[{idx}/{total}] [{category.upper()}] {question}")

        t0     = time.time()
        result = run_agent(question)
        elapsed = round(time.time() - t0, 2)

        actual_tools = [
            name for name, stats in result.get("telemetry", {}).items()
            if stats.get("calls", 0) > 0
        ]

        routing_correct = (
            set(actual_tools) == set(expected_tools)
            if expected_tools is not None else None
        )

        answer_ok = result.get("status") in ("answered", "direct_answer",
                                              "refused", "scope_clarification")
        icon = "✓" if answer_ok else "✗"

        print(f"  [{icon}] Status: {result['status']} | Steps: {result['steps_used']} "
              f"| Tools: {actual_tools} | {elapsed}s")
        print(f"  Answer : {result['final_answer'][:120]}...")

        if expected_tools:
            routing_icon = "✓" if routing_correct else "✗"
            print(f"  Routing [{routing_icon}] expected={expected_tools} actual={actual_tools}")

        results.append({
            "id":               item.get("id", idx) if isinstance(item, dict) else idx,
            "question":         question,
            "category":         category,
            "expected_tools":   expected_tools,
            "actual_tools":     actual_tools,
            "routing_correct":  routing_correct,
            "status":           result.get("status", "unknown"),
            "steps_used":       result.get("steps_used", 0),
            "final_answer":     result.get("final_answer", ""),
            "answer_preview":   result.get("final_answer", "")[:200],
            "elapsed_s":        elapsed,
            "expected_behavior": expected_beh,
        })

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    statuses = {
        "answered":           sum(1 for r in results if r["status"] == "answered"),
        "direct_answer":      sum(1 for r in results if r["status"] == "direct_answer"),
        "refused":            sum(1 for r in results if r["status"] == "refused"),
        "scope_clarification":sum(1 for r in results if r["status"] == "scope_clarification"),
        "cap_exceeded":       sum(1 for r in results if r["status"] == "cap_exceeded"),
    }

    print(f"Total questions : {len(results)}")
    for k, v in statuses.items():
        print(f"  {k:<22}: {v}")

    routing_rows = [r for r in results if r["routing_correct"] is not None]
    routing_ok   = sum(1 for r in routing_rows if r["routing_correct"])
    if routing_rows:
        pct = round(routing_ok / len(routing_rows) * 100)
        print(f"\nTool routing    : {routing_ok}/{len(routing_rows)} correct ({pct}%)")

    avg_steps = round(sum(r["steps_used"] for r in results) / len(results), 1) if results else 0
    avg_time  = round(sum(r["elapsed_s"]  for r in results) / len(results), 1) if results else 0
    print(f"Avg steps/query : {avg_steps}")
    print(f"Avg time/query  : {avg_time}s")

    # ── Per-category breakdown ────────────────────────────────────────────
    print("\nPer-category routing accuracy:")
    categories = sorted(set(r["category"] for r in results))
    for cat in categories:
        cat_rows = [r for r in results if r["category"] == cat and r["routing_correct"] is not None]
        if cat_rows:
            ok  = sum(1 for r in cat_rows if r["routing_correct"])
            pct = round(ok / len(cat_rows) * 100)
            print(f"  {cat:<20}: {ok}/{len(cat_rows)} ({pct}%)")

    # ── Save outputs ──────────────────────────────────────────────────────
    Path("eval").mkdir(exist_ok=True)

    out_json = Path("eval/results.json")
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    out_md = Path("eval/results.md")
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# IPL Agentic RAG — Evaluation Results\n\n")
        f.write(f"Total: {len(results)} questions\n\n")
        f.write("| # | Category | Question | Status | Steps | Tools | Routing | Time |\n")
        f.write("|---|----------|----------|--------|-------|-------|---------|------|\n")
        for r in results:
            routing = "✓" if r["routing_correct"] else ("✗" if r["routing_correct"] is False else "—")
            q_short = r["question"][:50].replace("|", "/")
            f.write(f"| {r['id']} | {r['category']} | {q_short} | {r['status']} "
                    f"| {r['steps_used']} | {r['actual_tools']} | {routing} | {r['elapsed_s']}s |\n")

        f.write("\n## Answers\n\n")
        for r in results:
            f.write(f"### Q{r['id']}: {r['question']}\n\n")
            f.write(f"**Category:** {r['category']}  \n")
            f.write(f"**Status:** {r['status']}  \n")
            f.write(f"**Steps:** {r['steps_used']}  \n")
            f.write(f"**Expected tools:** {r['expected_tools']}  \n")
            f.write(f"**Actual tools:** {r['actual_tools']}  \n")
            f.write(f"**Routing:** {'✓ Correct' if r['routing_correct'] else ('✗ Wrong' if r['routing_correct'] is False else '—')}  \n")
            f.write(f"**Expected behavior:** {r['expected_behavior']}  \n\n")
            f.write(f"**Answer:**\n{r['final_answer']}\n\n")
            f.write("---\n\n")

    print(f"\nSaved: {out_json}")
    print(f"Saved: {out_md}")


# ── Quick smoke test (5 key questions) ───────────────────────────────────────

def run_smoke_test() -> None:
    from agent import run_agent

    smoke = [
        ("Which team won IPL 2023?",                    "answered",      ["query_data"]),
        ("Who scored the most runs in IPL 2023?",       "answered",      ["query_data"]),
        ("Which team should I bet on?",                  "refused",       []),
        ("What happened in IPL 2019?",                   "refused",       []),
        ("Who is the current captain of Mumbai Indians?","answered",      ["web_search"]),
    ]

    print("\nSmoke Test — 5 key questions")
    print("=" * 70)
    passed = 0

    for q, expected_status, expected_tools in smoke:
        result = run_agent(q)
        actual_tools  = [n for n, s in result.get("telemetry", {}).items() if s.get("calls", 0) > 0]
        status_ok     = result["status"] == expected_status
        routing_ok    = set(actual_tools) == set(expected_tools) if expected_tools is not None else True
        ok            = status_ok and routing_ok
        passed       += int(ok)
        icon          = "✓" if ok else "✗"
        print(f"  [{icon}] {q[:60]}")
        print(f"       Status: {result['status']} (expected {expected_status})")
        print(f"       Tools : {actual_tools} (expected {expected_tools})")
        print(f"       Answer: {result['final_answer'][:100]}")

    print(f"\nSmoke test: {passed}/{len(smoke)} passed")


# ── Cache clear ───────────────────────────────────────────────────────────────

def clear_cache_cli() -> None:
    from utils.cache import clear_cache
    clear_cache()
    print("Cache cleared.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    try:
        if "--clear-cache" in args:
            clear_cache_cli()
            args = [a for a in args if a != "--clear-cache"]
            if not args:
                return

        if "--eval" in args:
            fresh = "--fresh" in args
            run_eval(fresh=fresh)

        elif "--test" in args:
            run_smoke_test()

        else:
            question = " ".join(args).strip()
            if not question:
                print("ERROR: Empty question.")
                sys.exit(1)
            run_single(question)

    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
    except Exception as exc:
        print(f"\nFatal error: {exc}")
        raise


if __name__ == "__main__":
    main()