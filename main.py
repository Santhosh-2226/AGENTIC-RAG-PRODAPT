"""
main.py

CLI entry point.
Usage:
    python main.py "Who scored the most runs in IPL 2023?"
    python main.py --eval
    python main.py --clear-cache
"""

import json
import sys
import time
from pathlib import Path


def run_single(question: str) -> None:
    from agent import run_agent

    print(f"\nQuestion: {question}")
    print("-" * 80)

    result = run_agent(question)

    print("\nAnswer:")
    print(result["final_answer"])

    if result.get("citations"):
        print("\nCitations:")
        for citation in result["citations"]:
            print(f"  - {citation}")

    print(f"\nStatus    : {result['status']}")
    print(f"Steps used: {result['steps_used']}")

    if result.get("uncertainty"):
        print(f"Confidence: {result['uncertainty']}")

    reflection = result.get("reflection")
    if isinstance(reflection, dict):
        status = "PASSED" if reflection.get("passed") else "FAILED"
        issue = reflection.get("issue", "")
        print(f"Reflection: {status}" + (f" — {issue}" if issue else ""))

    telemetry = result.get("telemetry", {})
    if telemetry:
        print("\nTool telemetry:")
        for tool_name, stats in telemetry.items():
            calls = stats.get("calls", 0)
            avg_latency_ms = stats.get("avg_latency_ms", 0)
            print(f"  {tool_name}: {calls} calls, avg {avg_latency_ms} ms")

    trace_path = result.get("trace_path")
    if trace_path:
        print(f"\nTrace saved: {trace_path}")

    print()


def run_eval() -> None:
    from agent import run_agent

    eval_path = Path("eval/questions.json")
    if not eval_path.exists():
        print("Missing eval/questions.json")
        return

    with eval_path.open("r", encoding="utf-8") as f:
        questions = json.load(f)

    if not isinstance(questions, list) or not questions:
        print("eval/questions.json must contain a non-empty list.")
        return

    results = []
    print(f"\nRunning evaluation on {len(questions)} questions")
    print("=" * 80)

    for idx, item in enumerate(questions, start=1):
        if isinstance(item, str):
            question = item
            category = "unknown"
            expected_tools = []
        else:
            question = item.get("question", "").strip()
            category = item.get("category", "unknown")
            expected_tools = item.get("expected_tools", [])

        if not question:
            print(f"\n[{idx}] Skipping empty question entry.")
            continue

        print(f"\n[{idx}/{len(questions)}] [{category}] {question}")
        start = time.time()
        result = run_agent(question)
        elapsed = round(time.time() - start, 2)

        actual_tools = [
            tool_name
            for tool_name, stats in result.get("telemetry", {}).items()
            if stats.get("calls", 0) > 0
        ]

        routing_correct = None
        if expected_tools:
            routing_correct = set(actual_tools) == set(expected_tools)

        row = {
            "question": question,
            "category": category,
            "expected_tools": expected_tools,
            "actual_tools": actual_tools,
            "routing_correct": routing_correct,
            "status": result.get("status", "unknown"),
            "steps_used": result.get("steps_used", 0),
            "answer_preview": result.get("final_answer", "")[:200],
            "elapsed_s": elapsed,
        }
        results.append(row)

        icon = "✓" if result.get("status") == "answered" else "✗"
        print(
            f"  [{icon}] Status: {row['status']} | "
            f"Steps: {row['steps_used']} | "
            f"Tools: {actual_tools} | "
            f"{elapsed}s"
        )

    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")

    total = len(results)
    answered = sum(1 for r in results if r["status"] == "answered")
    refused = sum(1 for r in results if r["status"] == "refused")
    direct = sum(1 for r in results if r["status"] == "direct_answer")
    cap_hit = sum(1 for r in results if r["status"] == "cap_exceeded")
    scope = sum(1 for r in results if r["status"] == "scope_clarification")

    print(f"Total      : {total}")
    print(f"Answered   : {answered}")
    print(f"Direct     : {direct}")
    print(f"Refused    : {refused}")
    print(f"Scope ask  : {scope}")
    print(f"Cap hit    : {cap_hit}")

    routing_rows = [r for r in results if r["routing_correct"] is not None]
    routing_ok = sum(1 for r in routing_rows if r["routing_correct"] is True)
    if routing_rows:
        print(f"Routing OK : {routing_ok}/{len(routing_rows)}")

    Path("eval").mkdir(exist_ok=True)

    out_json = Path("eval/results.json")
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    out_md = Path("eval/results.md")
    with out_md.open("w", encoding="utf-8") as f:
        f.write("# Evaluation Results\n\n")
        for r in results:
            f.write(f"## {r['question']}\n")
            f.write(f"- Category: {r['category']}\n")
            f.write(f"- Status: {r['status']}\n")
            f.write(f"- Steps used: {r['steps_used']}\n")
            f.write(f"- Expected tools: {r['expected_tools']}\n")
            f.write(f"- Actual tools: {r['actual_tools']}\n")
            f.write(f"- Routing correct: {r['routing_correct']}\n")
            f.write(f"- Elapsed: {r['elapsed_s']}s\n")
            f.write(f"- Answer preview: {r['answer_preview']}\n\n")

    print(f"\nSaved: {out_json}")
    print(f"Saved: {out_md}")


def clear_cache_cli() -> None:
    from utils.cache import clear_cache

    clear_cache()
    print("Cache cleared.")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py 'your question'")
        print("  python main.py --eval")
        print("  python main.py --clear-cache")
        sys.exit(0)

    arg = sys.argv[1]

    try:
        if arg == "--eval":
            run_eval()
        elif arg == "--clear-cache":
            clear_cache_cli()
        else:
            question = " ".join(sys.argv[1:]).strip()
            if not question:
                print("Question is empty.")
                sys.exit(1)
            run_single(question)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(1)
    except Exception as exc:
        print(f"\nFatal error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()