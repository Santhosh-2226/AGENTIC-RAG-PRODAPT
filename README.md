# 🏏 IPL Agentic RAG — Cricket Intelligence System

<p align="center">
  <img src="https://img.shields.io/badge/AI-Agentic%20RAG-blue?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Python-3.11-green?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Database-SQLite-orange?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Retrieval-FAISS%20%7C%20BM25-purple?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Status-In%20Progress-yellow?style=for-the-badge"/>
</p>

<p align="center">
  <b>Multi-source AI system that retrieves, reasons, and answers IPL queries with grounded data.</b>
</p>

---

## 🔗 Repository

👉 https://github.com/Santhosh-2226/AGENTIC-RAG-PRODAPT

---

## 🚀 Overview

This project implements an **Agentic RAG system** that answers IPL cricket queries by intelligently selecting between:

* 📊 Structured data (SQLite)
* 📄 Unstructured documents (PDF corpus)
* 🌐 Live web data (Tavily API)

Unlike traditional chatbots, this system:

* **does not hallucinate answers**
* **retrieves from real sources**
* **explains where answers come from**

---

## 🧠 Core Idea

> **Don’t generate answers. Retrieve → reason → compose.**

The system ensures:

* source-grounded responses
* controlled reasoning steps
* explicit uncertainty handling

---

## 🏗️ Architecture Overview

<p align="center">
  <img src="docs/architecture/ipl-agentic-rag-overview.png" width="900"/>
</p>

---

## ⚙️ Tech Stack

### 🔹 Core

* Python 3.11

### 🔹 Data & Storage

* SQLite (structured IPL data)
* pandas

### 🔹 Retrieval

* FAISS (semantic search)
* BM25 (keyword search)

### 🔹 NLP & Embeddings

* sentence-transformers (MiniLM)

### 🔹 Document Processing

* PyMuPDF

### 🔹 Web Layer

* Tavily API

### 🔹 LLM

* Anthropic Claude (Haiku / Sonnet)

### 🔹 Utilities

* diskcache
* python-dotenv

---

## 🧩 System Components

### 🔧 Tools Layer

| Tool          | Purpose                           |
| ------------- | --------------------------------- |
| `query_data`  | SQL-based statistical queries     |
| `search_docs` | Document retrieval (FAISS + BM25) |
| `web_search`  | Real-time information             |

---

### 🧠 Reasoning Layers

* Gatekeeper (input validation)
* Normalizer (intent + time detection)
* Goal Decomposer (task splitting)
* Sufficiency Checker (stopping condition)
* Composer (answer generation)
* Citation Binder (source mapping)
* Reflection (self-check)
* Uncertainty (confidence reporting)

---

### 🧩 Memory

* Evidence tracking
* Duplicate prevention
* Tool call history

---

## ⏱️ Temporal Intelligence

The system classifies queries into:

| Zone   | Description     | Tool Used |
| ------ | --------------- | --------- |
| Zone 1 | Historical      | DB / Docs |
| Zone 2 | Dataset-covered | DB / Docs |
| Zone 3 | Current / Live  | Web       |

---

## 🔄 Execution Flow

```text
User Query
   ↓
Normalization
   ↓
Goal Decomposition
   ↓
Agent Loop (max 8 steps)
   ↓
Tool Execution
   ↓
Evidence Memory
   ↓
Answer Composition
   ↓
Citation Binding
   ↓
Reflection + Uncertainty
```

---

## 📊 Data Pipeline

```text
CSV (data/raw/)
   ↓
ingest_data.py
   ↓
SQLite (ipl.db)
   ↓
query_data.py
```

---

## 📁 Project Structure

```text
ipl-agentic-rag/
├── agent.py
├── tools/
├── layers/
├── memory/
├── data/
├── ingest/
├── traces/
├── cache/
├── eval/
├── README.md
└── DESIGN.md
```

---

## 🧪 Example Queries

```text
Who scored the most runs in IPL 2023?
Compare Virat Kohli and Rohit Sharma.
Why did RCB struggle in 2023?
Who is the CSK captain now?
```

---

## ⚠️ System Constraints

* 🔒 Max 8 tool calls
* 🌐 Max 2 web calls
* ❌ No answer without evidence
* 🚫 Graceful refusal when data unavailable

---

## 📈 Current Status

| Module             | Status         |
| ------------------ | -------------- |
| Architecture       | ✅ Complete     |
| Data Ingestion     | ✅ Done         |
| query_data Tool    | ✅ Working      |
| Agent Loop         | 🚧 In Progress |
| Document Retrieval | 🚧 Pending     |

---

## 🧾 Traceability

Each query produces:

* tool call logs
* reasoning steps
* final answer
* citations

📁 Stored in:

```text
traces/
```

---

## 🎯 Design Philosophy

> **Keep the agent simple. Push complexity into tools.**

This ensures:

* clean architecture
* easy debugging
* scalability

---

## 🧠 Key Takeaway

This project demonstrates:

* Agentic AI systems
* Multi-source reasoning
* Real-world RAG pipelines
* Explainable AI design

---

## 👤 Author

**Your Name**
B.Tech — Artificial Intelligence & Data Science


# IPL Agentic RAG

An LLM agent that answers IPL cricket questions over mixed data sources:
structured statistics (SQLite), unstructured documents (PDFs), and live web search.

Built for the CIT Agentic RAG internship assignment — Option B (Sports Season Data).
Corpus: IPL 2022 and IPL 2023.

---

## What It Does

The agent receives a question, decides which tool(s) to call, retrieves evidence,
composes a grounded answer with exact citations, and stops gracefully when it cannot help.

Every decision in the loop is traceable. Every claim in the answer is bound to a source.

---

## Architecture (12 Layers)

```
Question → Cache → Gatekeeper → Normalizer → Goal Decomposer
→ Planning Step → Agent Loop (max 8 calls)
  → Tool Selector → Duplicate Guard → Tool Execution → Evidence Memory
  → Freshness Guard → Sufficiency Checker
→ Answer Composer → Citation Binder → Reflection → Uncertainty Statement
→ Trace Writer → Cache Store → Final Answer
```

Three tools:
- `search_docs` — hybrid BM25 + FAISS search over IPL PDF corpus
- `query_data`  — safe SQL generation against SQLite stats database
- `web_search`  — Tavily live search for current/recent information only

---

## Setup

```bash
# 1. Clone and install
git clone <your-repo-url>
cd ipl-agentic-rag
pip install -r requirements.txt

# 2. Set API keys
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and TAVILY_API_KEY

# 3. Add your data
# - Place IPL 2022/2023 CSV files in data/raw/
# - Place IPL PDF documents in data/docs/

# 4. Ingest data (run once)
python ingest/ingest_data.py    # builds data/ipl.db
python ingest/ingest_docs.py    # builds data/index/ (FAISS + BM25)

# 5. Verify each tool independently before running the agent
python tools/query_data.py      # manually check 3 questions
python tools/search_docs.py     # manually check 5 queries
python tools/web_search.py      # manually check web returns results
```

---

## Running the Agent

```bash
# Single question
python main.py "Who scored the most runs in IPL 2023?"

# Full evaluation set (20 questions)
python main.py --eval

# Clear cache (useful during development)
python main.py --clear-cache
```

---

## Data Requirements

**Structured (data/raw/):**
- `each_match_records-2023.csv`
- `IPL_Matches_2022.csv`
- `each_ball_records-2023.csv`
- `IPL_Ball_by_Ball_2022.csv`

Source: Kaggle IPL Complete Dataset (free download)

**Unstructured (data/docs/):**
- IPL 2022 and 2023 season review PDFs (iplt20.com)
- Wikipedia match report PDFs
- ESPNCricinfo season summary articles saved as PDF

Minimum: 10 PDF documents covering both seasons.

---

## CSV Files Required

Place these in `data/raw/` before running `ingest_data.py`:

| File | Source |
|------|--------|
| `each_match_records-2023.csv` | Kaggle IPL 2023 dataset |
| `IPL_Matches_2022.csv` | Kaggle IPL Complete dataset |
| `each_ball_records-2023.csv` | Kaggle IPL 2023 dataset |
| `IPL_Ball_by_Ball_2022.csv` | Kaggle IPL Complete dataset |

---

## Trace Format

Every run writes a JSON trace to `traces/`. Example:

```json
{
  "question": "Who scored most runs in IPL 2023?",
  "plan": "Plan: Use query_data. Sub-goals: retrieve top run scorer. Corpus is sufficient.",
  "steps": [
    {
      "step": 1,
      "tool": "query_data",
      "input": {"question": "top run scorer IPL 2023", "table_hint": "batting"},
      "result": {"rows": [{"player": "Shubman Gill", "runs": 890}], "row_count": 1},
      "latency_ms": 312,
      "success": true
    }
  ],
  "steps_used": "1 / 8 max",
  "final_answer": "Shubman Gill scored the most runs in IPL 2023 with 890 runs (database: batting_stats).",
  "citations": ["query_data → batting_stats table (1 rows matched)"],
  "status": "answered",
  "uncertainty": "Based on 1 source call (['query_data']). Corpus is sufficient.",
  "telemetry": {
    "query_data": {"calls": 1, "avg_latency_ms": 312, "failures": 0}
  }
}
```

---

## Known Failure Modes

**1. Wrong tool on ambiguous questions**
Questions like "How did Kohli do?" without a year or metric cause the agent to assume
batting stats for 2023. The assumption is stated in the answer, but it may not match
what the user intended. Fix: the normalizer states its assumption explicitly.

**2. Empty SQL results for obscure players**
If a player name is slightly misspelled or does not exist in the corpus years,
`query_data` returns zero rows. The agent reports "no data found" honestly rather
than hallucinating. This is correct behavior but may frustrate users expecting an answer.

**3. Web search rate limits**
Tavily free tier allows ~1000 searches/month. During heavy evaluation runs,
the cache prevents repeated calls. Clear the cache only when testing new questions.

**4. PDF chunking quality**
Low-quality or scanned PDFs produce noisy chunks. PyMuPDF handles standard PDFs well
but may fail on image-only PDFs. Pre-verify your PDFs open correctly with a PDF reader.

**5. Loop-inducing questions hit cap at 8**
Questions with no answer in any source exhaust all 8 tool calls and return a structured
refusal. This is the correct behavior — the cap fires exactly as required.

---

## Bonus Features Implemented

- **Bonus A**: Planning step before every loop (logged in trace)
- **Bonus B**: Per-tool telemetry in every trace (latency + call count + failures)
- **Bonus C**: Reflection step after answer composition (before/after logged)
- **Bonus D**: Run `python main.py --eval` with half your docs removed to test degradation

---

## API Cost Estimate

| Model | Usage | Approx cost |
|-------|-------|-------------|
| Claude Haiku | All internal steps (8 calls × 20 questions) | ~₹50 |
| Claude Sonnet | Final answer synthesis (1 call × 20 questions) | ~₹200 |
| Tavily | Web searches (max 40 calls total) | Free tier |
| FAISS / BM25 | Local — zero cost | ₹0 |
| SQLite | Local — zero cost | ₹0 |

Total estimated evaluation run: **under ₹300**

Cache hits on repeated questions cost nothing.

---

## Project Structure

```
ipl-agentic-rag/
├── agent.py              — main loop (~100 lines, fully explainable)
├── main.py               — CLI entry point
├── tools/
│   ├── search_docs.py    — FAISS + BM25 hybrid retrieval
│   ├── query_data.py     — SQLite + safe SQL generation
│   └── web_search.py     — Tavily wrapper (Zone 3 only)
├── layers/
│   ├── gatekeeper.py     — trivial/refuse/out-of-scope detection
│   ├── normalizer.py     — zone, intent, entity, compound splitting
│   ├── goal_decomposer.py — sub-goal tree builder
│   ├── sufficiency.py    — loop exit decision
│   ├── composer.py       — slot-based answer builder
│   ├── citation.py       — evidence-only citation binder
│   ├── reflection.py     — Bonus C: answer self-check
│   └── uncertainty.py    — honest quality statement
├── memory/
│   └── evidence.py       — evidence store + duplicate guard
├── ingest/
│   ├── ingest_data.py    — CSV → SQLite
│   └── ingest_docs.py    — PDF → FAISS + BM25 index
├── utils/
│   ├── cache.py          — file-based JSON cache
│   └── tracer.py         — trace writer + Bonus B telemetry
├── data/
│   ├── raw/              — CSV files (not committed)
│   ├── docs/             — PDF corpus (not committed)
│   └── index/            — FAISS index (not committed, rebuilt by ingest)
├── traces/               — per-run JSON traces (not committed)
├── cache/                — answer cache (not committed)
├── eval/
│   ├── questions.json    — 20 evaluation questions
│   └── results.json      — actual agent outputs (generated by --eval)
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── DESIGN.md
└── EVALUATION.md
```