"""
utils/tracer.py

Writes structured trace for every agent run.
Format matches exactly what the assignment PDF specifies on page 4.
Also captures Bonus B telemetry: latency + call count per tool.
"""

import json
import os
from datetime import datetime
from pathlib import Path

TRACES_DIR = Path(__file__).resolve().parent.parent / "traces"


class Tracer:
    def __init__(self, question: str):
        self.question = question
        self.steps = []
        self.plan = None
        self.timestamp = datetime.now().isoformat()

        # Bonus B telemetry — per-tool stats
        self.telemetry = {}

    # ── Logging methods ───────────────────────────────────────────────────

    def log_plan(self, plan: str) -> None:
        """Bonus A: store the pre-loop plan."""
        self.plan = plan

    def log_step(self, step_num: int, tool: str, tool_input: dict,
                 result: dict, latency_ms: int, success: bool) -> None:
        """Log one tool call with full input/output and timing."""
        self.steps.append({
            "step": step_num,
            "tool": tool,
            "input": tool_input,
            "result": _truncate_result(result),
            "latency_ms": latency_ms,
            "success": success
        })

        # Bonus B telemetry accumulation
        if tool not in self.telemetry:
            self.telemetry[tool] = {
                "calls": 0,
                "total_latency_ms": 0,
                "avg_latency_ms": 0,
                "failures": 0
            }
        self.telemetry[tool]["calls"] += 1
        self.telemetry[tool]["total_latency_ms"] += latency_ms
        self.telemetry[tool]["avg_latency_ms"] = round(
            self.telemetry[tool]["total_latency_ms"] / self.telemetry[tool]["calls"]
        )
        if not success:
            self.telemetry[tool]["failures"] += 1

    def log_cache_hit(self) -> None:
        self.steps.append({
            "step": 0,
            "tool": "cache",
            "input": {"question": self.question},
            "result": "CACHE_HIT",
            "latency_ms": 0,
            "success": True
        })

    def log_duplicate_blocked(self, tool: str, tool_input: dict) -> None:
        self.steps.append({
            "step": len(self.steps) + 1,
            "tool": tool,
            "input": tool_input,
            "result": "BLOCKED: duplicate call",
            "latency_ms": 0,
            "success": False,
            "note": "Duplicate guard fired — same tool+input already called."
        })

    def log_zone_override(self, blocked_tool: str) -> None:
        self.steps.append({
            "step": len(self.steps) + 1,
            "tool": blocked_tool,
            "input": {},
            "result": "BLOCKED: Zone 3 violation — web_search must go first",
            "latency_ms": 0,
            "success": False,
            "note": "Zone enforcement: question asks about current info."
        })

    def log_tool_error(self, tool: str, tool_input: dict, error: str) -> None:
        self.steps.append({
            "step": len(self.steps) + 1,
            "tool": tool,
            "input": tool_input,
            "result": f"ERROR: {error}",
            "latency_ms": 0,
            "success": False
        })

    # ── Finalize and save ─────────────────────────────────────────────────

    def finalize(
        self,
        answer,
        citations: list,
        status: str,
        uncertainty: str = "",
        steps_used: int = 0,
        reflection: dict = None
    ) -> dict:
        """
        Build final output dict in PDF-specified format and save to traces/.
        """
        # Handle answer being a string or a dict
        answer_text = (
            answer if isinstance(answer, str)
            else answer.get("answer_text", str(answer))
        )

        # Ensure citations are strings
        citation_strings = []
        for c in (citations or []):
            citation_strings.append(c if isinstance(c, str) else json.dumps(c))

        output = {
            # ── PDF format (page 4) ──────────────────────────────────────
            "question": self.question,
            "plan": self.plan,
            "steps": self.steps,
            "steps_used": f"{steps_used} / 8 max",
            "final_answer": answer_text,
            "citations": citation_strings,
            "status": status,

            # ── Extra layers ─────────────────────────────────────────────
            "uncertainty": uncertainty,
            "reflection": reflection,

            # ── Bonus B telemetry ─────────────────────────────────────────
            "telemetry": self.telemetry,

            "timestamp": self.timestamp
        }

        # Save trace to file
        TRACES_DIR.mkdir(parents=True, exist_ok=True)
        safe_q = "".join(c for c in self.question[:40] if c.isalnum() or c == " ").strip()
        safe_q = safe_q.replace(" ", "_")
        filename = TRACES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_q}.json"
        with open(filename, "w") as f:
            json.dump(output, f, indent=2, default=str)

        return output

    def print_trace(self, output: dict) -> None:
        """Print trace to terminal in human-readable format (for demos)."""
        print(f"\n{'='*60}")
        print(f"Question: {output['question']}")
        if output.get("plan"):
            print(f"\nPlan: {output['plan']}")
        print(f"\n--- Steps ---")
        for step in output["steps"]:
            tool = step["tool"]
            status = "✓" if step["success"] else "✗"
            note = step.get("note", "")
            print(f"  Step {step['step']}: [{status}] {tool}")
            if isinstance(step["result"], str) and len(step["result"]) < 100:
                print(f"    Result: {step['result']}")
            print(f"    Latency: {step['latency_ms']}ms")
            if note:
                print(f"    Note: {note}")
        print(f"\n--- Answer ---")
        print(output["final_answer"])
        print(f"\n--- Citations ---")
        for c in output["citations"]:
            print(f"  • {c}")
        print(f"\nSteps used: {output['steps_used']}")
        print(f"Status: {output['status']}")
        if output.get("uncertainty"):
            print(f"Uncertainty: {output['uncertainty']}")
        if output.get("telemetry"):
            print(f"\n--- Telemetry (Bonus B) ---")
            for tool, stats in output["telemetry"].items():
                print(f"  {tool}: {stats['calls']} calls, "
                      f"avg {stats['avg_latency_ms']}ms, "
                      f"{stats['failures']} failures")
        print("="*60)


# ── Helper ────────────────────────────────────────────────────────────────────

def _truncate_result(result: dict, max_chars: int = 500) -> dict:
    """
    Truncate large results for the trace file.
    Full data stays in evidence memory; trace stores a preview.
    """
    if not isinstance(result, dict):
        return result

    truncated = {}
    for k, v in result.items():
        if isinstance(v, str) and len(v) > max_chars:
            truncated[k] = v[:max_chars] + "... [truncated]"
        elif isinstance(v, list) and len(v) > 5:
            truncated[k] = v[:3]
            truncated[f"{k}_total"] = len(v)
        else:
            truncated[k] = v
    return truncated