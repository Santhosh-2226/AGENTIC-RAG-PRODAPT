import os
import requests
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
MAX_QUERY_WORDS = 10

CRICKET_DOMAINS = [
    "cricbuzz.com",
    "espncricinfo.com",
    "crictracker.com",
    "iplt20.com",
]

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None


def fetch_orange_cap_from_cricbuzz() -> str:
    """Fetch Orange Cap holder from Cricbuzz API (JSON, no JS rendering needed)."""
    url = "https://www.cricbuzz.com/api/html/cricket-series/9237/ipl-2026/stats"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/html",
        "Referer": "https://www.cricbuzz.com"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")

        rows = soup.select("div.cb-stats-player-sect")
        if rows:
            first = rows[0]
            name = first.select_one("a.cb-stats-player-name")
            runs = first.select_one("span.cb-stats-player-runs")
            team = first.select_one("span.cb-stats-player-team")

            name_text = name.get_text(strip=True) if name else "N/A"
            runs_text = runs.get_text(strip=True) if runs else "N/A"
            team_text = team.get_text(strip=True) if team else "N/A"

            return f"🟠 Orange Cap (IPL 2026): {name_text} ({team_text}) — {runs_text} runs"

        return None  # fallback to Tavily

    except Exception as e:
        return None  # fallback to Tavily


def fetch_orange_cap_via_tavily() -> str:
    """Fallback: Use Tavily to fetch directly from crictracker orange cap page."""
    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        response = tavily.search(
            query="IPL 2026 orange cap holder most runs current",
            search_depth="advanced",
            max_results=1,
            include_answer=True,
            include_domains=["crictracker.com", "espncricinfo.com", "cricbuzz.com"],
        )

        # ✅ Trust Tavily's direct AI answer
        answer = response.get("answer", "")
        if answer:
            return f"🟠 Orange Cap (IPL 2026): {answer}"

        # Fallback to first snippet
        results = response.get("results", [])
        if results:
            snippet = results[0].get("content", "")[:300]
            return f"🟠 From {results[0]['url']}:\n{snippet}"

        return "❌ Could not find Orange Cap data."

    except Exception as e:
        return f"❌ Tavily error: {str(e)}"


def web_search(query: str, reason: str) -> dict:
    query = (query or "").strip()
    reason = (reason or "").strip()

    base_response = {
        "query": query,
        "reason": reason,
        "direct_answer": None,
        "results": [],
        "result_count": 0,
        "error": None
    }

    if not query:
        base_response["error"] = "Empty query provided."
        return base_response

    if not TAVILY_API_KEY:
        base_response["error"] = "TAVILY_API_KEY not set."
        return base_response

    if TavilyClient is None:
        base_response["error"] = "tavily-python not installed."
        return base_response

    if len(query.split()) > MAX_QUERY_WORDS:
        query = " ".join(query.split()[:MAX_QUERY_WORDS])
        base_response["query"] = query

    # 🟠 Orange Cap detection
    orange_cap_kw = ["orange cap", "top scorer", "leading run scorer"]
    if any(kw in query.lower() for kw in orange_cap_kw):
        answer = fetch_orange_cap_from_cricbuzz()  # try scraping first
        if not answer:
            answer = fetch_orange_cap_via_tavily()  # fallback to Tavily
        base_response["direct_answer"] = answer
        return base_response

    # 🔵 Purple Cap detection
    purple_cap_kw = ["purple cap", "most wickets", "top wicket", "leading wicket"]
    if any(kw in query.lower() for kw in purple_cap_kw):
        try:
            tavily = TavilyClient(api_key=TAVILY_API_KEY)
            response = tavily.search(
                query="IPL 2026 purple cap holder most wickets current",
                search_depth="advanced",
                max_results=1,
                include_answer=True,
                include_domains=["crictracker.com", "espncricinfo.com", "cricbuzz.com"],
            )
            answer = response.get("answer", "")
            base_response["direct_answer"] = f"🟣 Purple Cap (IPL 2026): {answer}" if answer else "❌ Not found."
        except Exception as e:
            base_response["error"] = str(e)
        return base_response

    # 🏏 General IPL question
    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        response = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=3,
            include_answer=True,
            include_domains=["cricbuzz.com", "espncricinfo.com", "crictracker.com", "iplt20.com"],
        )

        answer = response.get("answer", None)
        base_response["direct_answer"] = answer

        results = []
        for item in response.get("results", [])[:3]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", "")[:400],
                "date": item.get("published_date", "unknown")
            })

        base_response["results"] = results
        base_response["result_count"] = len(results)

    except Exception as e:
        base_response["error"] = f"Tavily search failed: {str(e)}"

    return base_response
if __name__ == "__main__":
    print("\n🏏 IPL 2026 Search Assistant")
    print("=" * 60)
    print("Type your IPL question and press Enter.")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        question = input("Ask any IPL question: ").strip()

        if not question:
            print("⚠️  Please enter a question.\n")
            continue

        if question.lower() in ["exit", "quit", "q", "bye"]:
            print("\n👋 Goodbye! Enjoy IPL 2026! 🏆\n")
            break

        result = web_search(question, "IPL cricket query")

        print(f"\n{'='*60}")
        print(f"Query : {result['query']}")
        print(f"{'='*60}")

        if result.get("direct_answer"):
            print(f"\n💡 Answer: {result['direct_answer']}\n")
        elif result["error"]:
            print(f"\n❌ Error: {result['error']}\n")
        else:
            if result["results"]:
                r = result["results"][0]
                print(f"\n📰 {r['title']}")
                print(f"🌐 {r['url']}")
                print(f"📝 {r['snippet']}\n")
            else:
                print("\n⚠️  No results found. Try rephrasing.\n")

        print()  # spacing between questions