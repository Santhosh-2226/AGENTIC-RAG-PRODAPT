"""
main.py

CLI entry point.
Usage:
    python main.py "Who scored the most runs in IPL 2023?"
    python main.py --eval          # run all 20 evaluation questions
    python main.py --clear-cache   # clear the answer cache
"""

import sys
import json
from pathlib import Path


def run_single(question: str):
    from agent import run_agent
    from utils.tracer import Tracer

    print(f"\nQuestion: {question}")
    print("-" * 60)

    result = run_agent(question)

    print(f"\nAnswer:\n{result['final_answer']}")
    print(f"\nCitations:")
    for c in result.get("citations", []):
        print(f"  • {c}")
    print(f"\nSteps used: {result['steps_used']}")
    print(f"Status    : {result['status']}")
    if result.get("uncertainty"):
        print(f"Confidence: {result['uncertainty']}")
    if result.get("reflection"):
        r = result["reflection"]
        status = "PASSED" if r.get("passed") else "FAILED"
        print(f"Reflection: {status}" + (f" — {r.get('issue', '')}" if not r.get("passed") else ""))
    if result.get("telemetry"):
        print("\nTool telemetry (Bonus B):")
        for tool, stats in result["telemetry"].items():
            print(f"  {tool}: {stats['calls']} calls, avg {stats['avg_latency_ms']}ms")
    print()


def run_eval():
    """Run all questions from eval/questions.json."""
    from agent import run_agent
    import time

    eval_path = Path("eval/questions.json")
    if not eval_path.exists():
        print("No eval/questions.json found. Create it first.")
        return

    with open(eval_path) as f:
        questions = json.load(f)

    results = []
    print(f"\nRunning evaluation: {len(questions)} questions\n{'='*60}")

    for i, q_entry in enumerate(questions):
        question = q_entry["question"]
        expected_tools = q_entry.get("expected_tools", [])
        category = q_entry.get("category", "unknown")

        print(f"\n[{i+1}/{len(questions)}] [{category}] {question}")
        start = time.time()
        result = run_agent(question)
        elapsed = round(time.time() - start, 2)

        # Check tool routing correctness
        tools_used = result.get("telemetry", {}).keys()
        routing_correct = all(t in tools_used for t in expected_tools) if expected_tools else None

        results.append({
            "question": question,
            "category": category,
            "expected_tools": expected_tools,
            "actual_tools": list(tools_used),
            "routing_correct": routing_correct,
            "status": result["status"],
            "steps_used": result["steps_used"],
            "answer_preview": result["final_answer"][:150],
            "elapsed_s": elapsed
        })

        status_icon = "✓" if result["status"] == "answered" else "✗"
        print(f"  [{status_icon}] Status: {result['status']} | Steps: {result['steps_used']} | {elapsed}s")

    # Summary
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    answered = sum(1 for r in results if r["status"] == "answered")
    refused = sum(1 for r in results if r["status"] == "refused")
    cap_hit = sum(1 for r in results if r["status"] == "cap_exceeded")
    print(f"  Answered   : {answered}/{len(results)}")
    print(f"  Refused    : {refused}")
    print(f"  Cap hit    : {cap_hit}")

    correct_routing = [r for r in results if r["routing_correct"] is True]
    print(f"  Correct tool routing: {len(correct_routing)}/{len(results)}")

    # Save results
    Path("eval").mkdir(exist_ok=True)
    out_path = Path("eval/results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py 'your question'")
        print("  python main.py --eval")
        print("  python main.py --clear-cache")
        sys.exit(0)

    arg = sys.argv[1]

    if arg == "--eval":
        run_eval()
    elif arg == "--clear-cache":
        from utils.cache import clear_cache
        clear_cache()
    else:
        question = " ".join(sys.argv[1:])
        run_single(question)


if __name__ == "__main__":
    main()