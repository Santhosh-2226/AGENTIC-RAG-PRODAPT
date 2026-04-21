"""
search_docs.py
==============
Hybrid retrieval (FAISS + BM25) + VERIFIED LLM answers
"""

from __future__ import annotations
import pickle, re, sys
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

# ── CONFIG ──────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent
INDEX_DIR   = BASE_DIR / "data" / "index"
FAISS_PATH  = INDEX_DIR / "faiss.index"
BM25_PATH   = INDEX_DIR / "bm25.pkl"
CHUNKS_PATH = INDEX_DIR / "chunks.json"

EMBED_MODEL = "all-MiniLM-L6-v2"
DEBUG = True   # 🔥 TURN ON/OFF DEBUG HERE

_model: SentenceTransformer | None = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model

# ────────────────────────────────────────────────────────
# LOAD INDEX
# ────────────────────────────────────────────────────────
_cache: dict[str, Any] = {}

def load_index():
    if _cache:
        return _cache["faiss"], _cache["chunks"], _cache["bm25"]

    import json
    fi = faiss.read_index(str(FAISS_PATH))
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    with open(BM25_PATH, "rb") as f:
        bm25 = pickle.load(f)

    _cache["faiss"], _cache["chunks"], _cache["bm25"] = fi, chunks, bm25
    return fi, chunks, bm25

# ────────────────────────────────────────────────────────
# UTILS
# ────────────────────────────────────────────────────────
def tokenize(text: str):
    return re.findall(r"[a-z0-9]+", text.lower())

# ────────────────────────────────────────────────────────
# SEARCH
# ────────────────────────────────────────────────────────
def search(query, top_k=5):
    fi, chunks, bm25 = load_index()
    model = get_model()

    # BM25
    bm25_scores = bm25.get_scores(tokenize(query))
    bm25_top = np.argsort(bm25_scores)[::-1][:20]

    # FAISS
    q_emb = model.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(q_emb)
    _, hits = fi.search(q_emb, 20)
    faiss_top = hits[0]

    # RRF fusion
    scores = {}
    for i, idx in enumerate(bm25_top):
        scores[idx] = scores.get(idx, 0) + 1/(60+i)
    for i, idx in enumerate(faiss_top):
        scores[idx] = scores.get(idx, 0) + 1/(60+i)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    for idx, score in ranked[:top_k]:
        chunk = chunks[idx]
        chunk["score"] = round(score, 4)
        results.append(chunk)

    return results

# ────────────────────────────────────────────────────────
# 🔥 VERIFIED LLM ANSWER
# ────────────────────────────────────────────────────────
def synthesize_answer(query, chunks):
    try:
        from groq import Groq
        import os
        from dotenv import load_dotenv

        load_dotenv()
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        # Build context with source info
        context = ""
        for i, c in enumerate(chunks[:3], 1):
            context += f"""
[Source {i}]
File: {c['source']}
Page: {c['page']}
Season: {c.get('season')}

{c['text'][:800]}
"""

        # STRICT PROMPT
        prompt = f"""
You MUST answer ONLY using the provided context.

If the exact answer is NOT clearly present,
reply ONLY: "Not found in documents."

Also include source in this format:
<answer> (Source: file_name, Page X)

DO NOT use outside knowledge.

Context:
{context}

Question: {query}

Answer:
"""

        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                temperature=0.2,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception:
            response = client.chat.completions.create(
                model="llama3-8b-8192",
                temperature=0.2,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"LLM failed: {e}"

# ────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────
def main():
    print("\n🏏 IPL RAG Search (Verified)\n")

    while True:
        q = input("Query > ").strip()
        if q.lower() in ["exit", "quit"]:
            break

        print("\n🔍 Searching...")
        results = search(q)

        if not results:
            print("⚠️ No results found\n")
            continue

        # 🔥 DEBUG: SHOW CHUNKS
        if DEBUG:
            print("\n📄 Retrieved Chunks:\n")
            for i, r in enumerate(results, 1):
                print(f"[{i}] {r['source']} | Page {r['page']} | Score: {r['score']}")
                print(r["text"][:200])
                print("-"*60)

        print("\n🤖 Generating answer...")
        answer = synthesize_answer(q, results)

        print("\n" + "="*60)
        print("💡 Answer:", answer)
        print("="*60 + "\n")

if __name__ == "__main__":
    main()