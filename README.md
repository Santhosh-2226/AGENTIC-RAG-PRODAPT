# IPL Agentic RAG — Cricket Intelligence System

<p align="center">
  <img src="docs/architecture.png" alt="Architecture Diagram" width="900"/>
</p>

[![Architecture](https://img.shields.io/badge/System-Agentic%20RAG-0f766e.svg)](#)
[![Reasoning](https://img.shields.io/badge/Focus-Grounded%20Reasoning-7c3aed.svg)](#)
[![Retrieval](https://img.shields.io/badge/Design-Multi--Source%20Retrieval-2563eb.svg)](#)

---

## Overview

IPL Agentic RAG is a **controlled, multi-source reasoning system** designed to answer IPL cricket queries using:

- **structured statistical data**
- **unstructured document corpus**
- **live web sources**

The system enforces:
- evidence-backed answers
- correct tool usage
- temporal correctness
- bounded reasoning
- explicit uncertainty handling

This is not a generative chatbot. It is a **retrieval-driven decision system**.

---

## Problem Being Solved

Standard LLM systems fail due to:

1. **Hallucination** — generating unsupported answers  
2. **Temporal errors** — answering current queries with stale data  
3. **Source mismatch** — using wrong data type for the question  

This system solves these by enforcing:
- strict tool routing
- time-aware retrieval
- evidence-based stopping conditions

---

## Core Design Principles

### 1. Evidence-Type Separation
- statistics → structured database  
- narrative → document corpus  
- current → web search  

---

### 2. Temporal Awareness
Every query is classified before retrieval:
- historical
- corpus-present
- current (true-present)

---

### 3. Controlled Agent Behavior
The system uses an agent loop with strict constraints:
- maximum **8 tool calls (hard cap)**
- no duplicate tool execution
- evidence-driven stopping
- graceful failure if unresolved

---

### 4. Grounded Answering
The system does **not generate answers freely**.  
It constructs answers only from retrieved evidence.

---

### 5. Traceability
Every query produces:
- plan
- tool sequence
- retrieved evidence
- final citations
- uncertainty statement

---

## Temporal Query Zones

### Zone 1 — Historical
Explicit past reference  
→ Use local data only

---

### Zone 2 — Corpus-Present
Covered by IPL 2023–2024 corpus  
→ Use local data

---

### Zone 3 — True-Present
Requires current information  
→ Web search is mandatory (first priority)

---

## System Architecture

---

### Stage 1 — Input Control

#### Cache Check
- Zone 1 → long cache  
- Zone 2 → medium cache  
- Zone 3 → short TTL or disabled  

---

#### Gatekeeper
Filters:
- invalid queries
- unsafe requests
- out-of-domain questions

---

#### Scope Trap Detection
Prevents broad queries:

Example:
> "Tell me everything about IPL 2024"

System response:
- asks user to narrow scope  
- **no tool calls wasted**

---

## Stage 2 — Query Understanding

---

### Entity Normalization
Examples:
- MI → Mumbai Indians  
- RCB → Royal Challengers Bengaluru  
- Virat → Virat Kohli  

---

### Intent Classification
- statistical  
- narrative  
- comparative  
- causal  
- current  
- multi-step  

---

### Temporal Zone Detection
Determines retrieval strategy before tool selection.

---

### Goal Decomposition
Breaks query into sub-goals.

Example:
> Compare Bumrah and Shami and explain performance

Sub-goals:
- Bumrah stats  
- Shami stats  
- commentary on Bumrah  
- commentary on Shami  

Each sub-goal remains **OPEN** until resolved.

---

### Complexity Gate
If query expands beyond limits:
- too many entities  
- too many aspects  
- too broad  

System stops and requests refinement.

---

## Stage 3 — Agent Planning and Tool Loop

---

### Planning Step
Before tool execution:
- system writes short plan  
- defines tool order  

---

### Tool Selection Logic

Priority:
1. `query_data` → statistics  
2. `search_docs` → narrative  
3. `web_search` → freshness  

Conditions:
- Zone 3 → web_search prioritized  
- unresolved sub-goals → continue loop  
- cost awareness → cheapest valid tool first  

---

### Duplicate Guard
- blocks repeated tool calls  
- avoids redundant retrieval  

---

### Tool Execution

The system uses **three tools only**.

---

## Tool Definitions and Data Extraction

---

### `query_data` — Structured Data

#### Data Source
- SQLite IPL database

#### Extraction Logic
1. Natural language query → SQL  
2. Validate schema (tables + columns)  
3. Allow only `SELECT` queries  
4. Enforce filters (season, player, etc.)  
5. Execute query  
6. Return structured output  

#### Output
- scalar or table  
- column names  
- row references  

---

### `search_docs` — Unstructured Data

#### Data Source
- IPL PDFs (match reports, analysis, reviews)

#### Extraction Logic
1. PDF → semantic chunks  
2. Metadata tagging:
   - source file
   - page number
   - season
   - entities  

3. Retrieval:
   - BM25 → keyword matching  
   - FAISS → semantic similarity  

4. Fusion:
   - combine rankings  
   - return top relevant chunks  

#### Output
- text chunk  
- file name  
- page number  
- season  

---

### `web_search` — Live Data

#### Data Source
- Tavily API

#### Extraction Logic
1. Generate short query  
2. Retrieve recent results  
3. Extract:
   - snippet  
   - URL  
   - publication date  

#### Output
- top results with metadata  

---

## Evidence Memory

After each tool call:

System stores:
- tool name  
- input  
- output  
- source  
- timestamp  
- linked sub-goals  

Used for:
- avoiding duplicate calls  
- tracking coverage  
- reasoning continuity  

---

## Freshness Guard

Condition:
- Zone 3 query  
- only old corpus evidence available  

Action:
- mark evidence as stale  
- force web search  

---

## Sufficiency Checker

After each step:

Checks:
- all sub-goals resolved?  
- comparison complete?  
- current info verified?  
- narrative support present?  
- numeric evidence present?  

---

### Decision

- YES → exit loop  
- NO → continue  

---

## Hard Cap (Critical Constraint)

- Maximum **8 tool calls**

If reached:
- stop execution immediately  
- trigger graceful fallback  

---

## Graceful Failure Handling

If system cannot resolve query:

Returns structured response:

- partial answer (if possible)  
- missing sub-goals clearly stated  
- reason for failure  

Example:
> "Searched database, documents, and web sources but could not find reliable evidence for this query within IPL 2023–2024 coverage."

No hallucination is allowed.

---

## Stage 4 — Grounded Answer Generation

---

### Slot-Based Composition

Answer is built using:

- statistical slot (from SQL)  
- narrative slot (from documents)  
- current slot (from web)  

LLM cannot fill missing slots.

---

### Citation Binding

Every claim is mapped:

- database → table + row  
- document → file + page  
- web → URL + date  

If no source:
- claim removed or marked uncertain  

---

### Uncertainty Communication

Final answer includes:

- number of sources  
- agreement/conflict  
- freshness status  
- unresolved gaps  

---

### Reflection Step

Checks:
- answer completeness  
- citation coverage  
- contradiction  
- temporal consistency  

If failed and steps remain:
- one more targeted retrieval  

---

## Stage 5 — Logging and Observability

---

### Trace Output

Each query produces:

- question  
- plan  
- tool calls  
- evidence  
- final answer  
- citations  
- steps used (out of 8)  
- uncertainty summary  

---

### Telemetry

Tracks:
- tool usage  
- latency  
- failure rates  

---

## Why This Architecture Works

This system avoids common RAG failures by enforcing:

- correct tool usage  
- time-aware retrieval  
- bounded reasoning  
- evidence-based answers  
- explicit failure handling  

---

## Limitations

- limited to IPL 2023–2024 corpus  
- NL-to-SQL semantic errors possible  
- web result quality varies  
- no semantic cache  
- document parsing noise  
- causal answers depend on available commentary  

---

## Future Improvements

- better embeddings  
- semantic caching  
- SQL validation improvements  
- trust ranking for web sources  
- larger dataset coverage  
- automated evaluation  

---

## Final Summary

IPL Agentic RAG is a **controlled retrieval and reasoning system** that:

- selects the correct data source  
- enforces temporal correctness  
- limits reasoning steps  
- avoids hallucination  
- provides traceable, evidence-backed answers  

It replaces blind generation with **structured, verifiable decision-making**.