"""
tools/web_search.py

Live web search using Tavily API.
Called ONLY for Zone 3 questions (current/live information).
Returns top-3 snippets with URL and publication date.
Hard limit: 2 calls per agent session (enforced in agent.py).
"""

import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


def web_search(query: str, reason: str) -> dict:
    """
    Main entry point for the web_search tool.

    Args:
        query: Short search query, under 10 words.
        reason: Why live data is needed (logged in trace).

    Returns:
        dict with results list (snippet, url, date) or error.
    """
    if not TAVILY_API_KEY:
        return {
            "error": "TAVILY_API_KEY not set in .env file.",
            "results": [],
            "query": query,
            "reason": reason
        }

    if len(query.split()) > 12:
        # Trim to keep it focused — Tavily works best with short queries
        query = " ".join(query.split()[:10])

    try:
        from tavily import TavilyClient
        tavily = TavilyClient(api_key=TAVILY_API_KEY)

        response = tavily.search(
            query=query,
            search_depth="basic",   # "basic" = faster + cheaper than "advanced"
            max_results=3,
            include_answer=False,   # raw snippets only, no LLM summary
        )

        results = []
        for item in response.get("results", [])[:3]:
            results.append({
                "snippet": item.get("content", "")[:400],  # cap length
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "date": item.get("published_date") or datetime.now().strftime("%Y-%m-%d")
            })

        return {
            "query": query,
            "reason": reason,
            "results": results,
            "result_count": len(results)
        }

    except ImportError:
        return {
            "error": "tavily-python not installed. Run: pip install tavily-python",
            "results": [],
            "query": query
        }
    except Exception as e:
        return {
            "error": f"Tavily search failed: {str(e)}",
            "results": [],
            "query": query,
            "reason": reason
        }


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("CSK captain IPL 2025", "User asked who is current CSK captain"),
        ("Virat Kohli retirement status 2025", "User asked if Kohli is retired"),
        ("IPL 2025 points table", "User asked for current standings"),
    ]
    for query, reason in tests:
        print(f"\nQuery: '{query}'")
        result = web_search(query, reason)
        if "error" in result:
            print(f"  ERROR: {result['error']}")
        else:
            print(f"  Results: {result['result_count']}")
            for r in result["results"]:
                print(f"  [{r['date']}] {r['url']}")
                print(f"   {r['snippet'][:120]}...")