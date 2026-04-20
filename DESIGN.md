# DESIGN.md
## IPL Agentic RAG — Agent Loop Design

---

## The Three Tools

### search_docs
**Purpose:** Semantic and lexical search over IPL PDF documents.

**Description written for the LLM:**
"Search IPL match reports, season reviews, player profiles, and expert commentary stored as PDF documents. Use when the question asks for narrative explanation, analyst opinion, tactical analysis, or historical context. Do NOT use for precise statistics or numbers — use query_data instead. Do NOT use for current or live information — use web_search instead."

**Input:** `query` (string), `season` (optional: '2022' or '2023'), `entity` (optional: player or team name)

**Output:** Top-3 text chunks, each with: `text`, `source` (filename), `page`, `season`, `freshness_date`

**Internal mechanics:**
1. BM25 retrieves top-20 chunks by lexical match
2. FAISS retrieves top-20 chunks by vector similarity (all-MiniLM-L6-v2 embeddings)
3. Reciprocal Rank Fusion merges both ranked lists
4. Season and entity metadata filters applied
5. Top-3 returned

---

### query_data
**Purpose:** Precise numerical statistics from the IPL 2022-2023 SQLite database.

**Description written for the LLM:**
"Query the IPL 2022-2023 structured statistics database. Use when the question asks for runs, wickets, averages, strike rates, economy rates, match results, rankings, or any measurable number. Do NOT use for opinions or narrative — use search_docs instead. Do NOT use for events after IPL 2023 — use web_search instead."

**Input:** `question` (string), `table_hint` (optional: 'batting', 'bowling', 'matches', 'players')

**Output:** `sql` (generated query), `columns`, `rows`, `row_count`, `table`, `scalar` (if single value)

**Internal mechanics:**
1. Real schema injected into generation prompt (prevents hallucinated column names)
2. Claude Haiku generates SQL
3. SQL validated: SELECT only, no DROP/DELETE/INSERT
4. Query executed against SQLite
5. Result formatted with source table and row count for citation binder

**Database tables:**
- `batting_stats(season, player, runs, balls_faced, innings, strike_rate)`
- `bowling_stats(season, player, balls_bowled, runs_conceded, wickets, overs, economy)`
- `matches(match_id, season, date, venue, team1, team2, toss_winner, toss_decision, winner, win_by_runs, win_by_wickets, player_of_match)`
- `deliveries(match_id, season, inning, over, ball, batting_team, bowling_team, batter, bowler, batsman_runs, extras, total_runs, is_wicket, player_dismissed, wicket_type)`
- `players(season, player)`

---

### web_search
**Purpose:** Live web search for current or recent information only.

**Description written for the LLM:**
"Search the live web. Use ONLY when the question asks about current, recent, or live information: current captain, today's news, injury updates, retirement status, 2024/2025 season info. Do NOT use for historical data available in the corpus. Maximum 2 calls per question."

**Input:** `query` (string, under 10 words), `reason` (string, why live data is needed)

**Output:** Top-3 results, each with: `snippet`, `url`, `title`, `date`

---

## The Agent Loop — Step by Step

The loop is a Python `while` with a step counter. Here is exactly what happens on each iteration:

```
WHILE step < 8:

  1. Call Claude Haiku with current messages + available tools
     - If web cap hit: web_search removed from available tools
  
  2. If stop_reason == "end_turn": Claude decided no tool needed → break
  
  3. Extract tool_use block from response
  
  4. Compute call_hash = MD5(tool_name + sorted_input)
     - If hash in memory.call_hashes → DUPLICATE GUARD fires
       → add warning message → step++ → continue
  
  5. If zone == 3 AND tool != web_search AND web_calls == 0 → ZONE GUARD fires
     → add zone warning message → step++ → continue
  
  6. If tool == web_search AND web_calls >= 2 → WEB CAP fires
     → add cap message → step++ → continue
  
  7. Execute tool (with one retry on exception)
     → Record latency_ms
  
  8. memory.add(tool, input, result, hash)
     memory.mark_duplicate(hash)
  
  9. goals = update_goals(goals, tool, result)
     → Closes matching OPEN goals if result has content
  
  10. tracer.log_step(step, tool, input, result, latency_ms, success)
  
  11. Append assistant message + tool_result to messages list
  
  12. step += 1
  
  13. if is_sufficient(goals, normalized, memory): break

IF step >= 8 AND open goals remain:
  → Return structured refusal (CapExceededError)
```

---

## How Infinite Loops Are Prevented

Three independent mechanisms, each enforced in code:

**1. Hard cap at 8 steps** — `while step < MAX_STEPS` with `MAX_STEPS = 8`. No way to exceed this. If cap is hit with open goals, a structured refusal is returned immediately with which sub-goals were unresolved and why.

**2. Duplicate guard** — Every tool call is hashed by `MD5(tool_name + json.dumps(input, sort_keys=True))`. The hash is checked before execution. If it already exists in `memory.call_hashes`, the call is blocked and a `DUPLICATE_CALL` message is injected into the conversation, forcing the model to try a different approach.

**3. Web call cap** — A separate `web_calls` counter tracks Tavily calls. Once it hits 2, `web_search` is removed from `available_tools` entirely for the rest of the session. The LLM cannot call it even if it tries.

---

## Temporal Zone System

Every question is classified into one of three zones before any tool runs:

| Zone | Meaning | First Tool |
|------|---------|------------|
| 1 | Historical — explicit past year in question | query_data or search_docs |
| 2 | Corpus-present — about 2022 or 2023 | query_data or search_docs |
| 3 | True present — "now", "currently", "latest" | web_search (mandatory) |

Zone 3 triggers the Zone Guard in the loop: if the agent tries to call a corpus tool before calling web_search, the call is blocked and a warning injected. This ensures current questions always get a live web result before any corpus data.

---

## Citation System

The citation binder pulls from `memory.all_sources()` only. It never allows the LLM to generate citation text from its own knowledge.

- `search_docs` result → `search_docs → {filename}, page {N} (IPL {season})`
- `query_data` result → `query_data → {table} table ({N} rows matched)`
- `web_search` result → `web_search → {url} (published {date})`

Any claim in the composed answer that cannot be traced to an evidence item is either removed by the composer prompt constraints or flagged in the uncertainty statement.

---

## Bonus Features

**Bonus A — Planning Step:** Before the loop starts, the agent writes a 1-3 sentence plan describing which tools it intends to use and why. The plan is stored in the trace. Accuracy is measured with vs without plan across the 20-question eval set.

**Bonus B — Per-Tool Telemetry:** Every `tracer.log_step()` call accumulates call count, total latency, average latency, and failure count per tool. The evaluation report includes a summary table.

**Bonus C — Reflection Step:** After composing the answer, Claude Haiku checks: does it address the question? Is every claim cited? Are there contradictions? If reflection fails and steps remain, one more targeted retrieval is triggered. Trace records before and after.

**Bonus D — Degradation Test:** Remove 7 documents from `data/docs/`, rebuild the index, rerun `python main.py --eval`. Compare results.json before and after to measure fallback behavior.