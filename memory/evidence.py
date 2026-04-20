"""
memory/evidence.py

Stores every tool result during an agent session.
Powers the duplicate guard, sufficiency checker, citation binder,
and uncertainty communicator.
One EvidenceMemory instance per agent run — reset between questions.
"""


class EvidenceMemory:
    def __init__(self):
        # All retrieved evidence items, in call order
        self.items = []
        # Set of call hashes — prevents duplicate (tool, input) calls
        self.call_hashes = set()

    # ── Adding evidence ───────────────────────────────────────────────────

    def add(self, tool_name: str, tool_input: dict,
            result: dict, call_hash: str) -> None:
        """Store a tool result with full metadata."""
        self.items.append({
            "tool": tool_name,
            "input": tool_input,
            "result": result,
            "hash": call_hash
        })

    # ── Duplicate guard ───────────────────────────────────────────────────

    def is_duplicate(self, call_hash: str) -> bool:
        """True if this exact (tool, input) combination was already called."""
        return call_hash in self.call_hashes

    def mark_duplicate(self, call_hash: str) -> None:
        """Mark a call hash as used after execution."""
        self.call_hashes.add(call_hash)

    # ── Retrieval helpers ─────────────────────────────────────────────────

    def get_by_tool(self, tool_name: str) -> list:
        """Return all evidence items from a specific tool."""
        return [i for i in self.items if i["tool"] == tool_name]

    def has_any_result(self) -> bool:
        """True if at least one tool was called successfully."""
        return len(self.items) > 0

    def has_successful_result(self, tool_name: str) -> bool:
        """True if the tool returned a result with no error."""
        for item in self.get_by_tool(tool_name):
            if "error" not in item["result"]:
                return True
        return False

    # ── Citation metadata ─────────────────────────────────────────────────

    def all_sources(self) -> list:
        """
        Returns all source metadata for the citation binder.
        Each source has type + exact reference (file+page, table+row, url+date).
        """
        sources = []

        for item in self.items:
            tool = item["tool"]
            result = item["result"]

            if tool == "search_docs":
                for chunk in result.get("chunks", []):
                    sources.append({
                        "type": "document",
                        "source": chunk.get("source", "unknown"),
                        "page": chunk.get("page", "?"),
                        "season": chunk.get("season", "unknown"),
                        "freshness_date": chunk.get("freshness_date", "unknown"),
                        "text_preview": chunk.get("text", "")[:80]
                    })

            elif tool == "query_data":
                sources.append({
                    "type": "database",
                    "table": result.get("table", "unknown"),
                    "sql": result.get("sql", ""),
                    "row_count": result.get("row_count", 0),
                    "question": result.get("question", "")
                })

            elif tool == "web_search":
                for r in result.get("results", []):
                    sources.append({
                        "type": "web",
                        "url": r.get("url", ""),
                        "title": r.get("title", ""),
                        "date": r.get("date", "unknown"),
                        "snippet_preview": r.get("snippet", "")[:80]
                    })

        return sources

    # ── Staleness check ───────────────────────────────────────────────────

    def oldest_document_season(self) -> str:
        """Returns the oldest season found in document results."""
        seasons = []
        for item in self.get_by_tool("search_docs"):
            for chunk in item["result"].get("chunks", []):
                s = chunk.get("season", "")
                if s and s.isdigit():
                    seasons.append(s)
        return min(seasons) if seasons else ""

    # ── Debug ─────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        """Quick summary for trace logging."""
        return {
            "total_calls": len(self.items),
            "tools_used": list(set(i["tool"] for i in self.items)),
            "search_docs_calls": len(self.get_by_tool("search_docs")),
            "query_data_calls": len(self.get_by_tool("query_data")),
            "web_search_calls": len(self.get_by_tool("web_search")),
        }