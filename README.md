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

👉 https://github.com/YOUR_USERNAME/ipl-agentic-rag

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
