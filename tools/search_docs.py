"""
tools/search_docs.py — agent-compatible wrapper around the hybrid retriever.
Returns {"chunks": [...]} format that the agent and citation binder expect.
The underlying FAISS+BM25 search logic is preserved exactly.
"""
from __future__ import annotations
import pickle
import re
import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

BASE_DIR    = Path(__file__).resolve().parent
INDEX_DIR   = BASE_DIR / "data" / "index"
FAISS_PATH  = INDEX_DIR / "faiss.index"
BM25_PATH   = INDEX_DIR / "bm25.pkl"
CHUNKS_PATH = INDEX_DIR / "chunks.json"

EMBED_MODEL = "all-MiniLM-L6-v2"

_model: SentenceTransformer | None = None
_cache: dict[str, Any] = {}


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def load_index():
    if _cache:
        return _cache["faiss"], _cache["chunks"], _cache["bm25"]
    fi = faiss.read_index(str(FAISS_PATH))
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    with open(BM25_PATH, "rb") as f:
        bm25 = pickle.load(f)
    _cache["faiss"], _cache["chunks"], _cache["bm25"] = fi, chunks, bm25
    return fi, chunks, bm25


def tokenize(text: str):
    return re.findall(r"[a-z0-9]+", text.lower())


def _hybrid_search(query: str, top_k: int = 5) -> list:
    """FAISS + BM25 hybrid search — unchanged from original."""
    fi, chunks, bm25 = load_index()
    model = get_model()

    bm25_scores = bm25.get_scores(tokenize(query))
    bm25_top    = np.argsort(bm25_scores)[::-1][:20]

    q_emb = model.encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(q_emb)
    _, hits   = fi.search(q_emb, 20)
    faiss_top = hits[0]

    scores = {}
    for i, idx in enumerate(bm25_top):
        scores[idx] = scores.get(idx, 0) + 1 / (60 + i)
    for i, idx in enumerate(faiss_top):
        scores[idx] = scores.get(idx, 0) + 1 / (60 + i)

    ranked  = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    results = []
    for idx, score in ranked[:top_k]:
        chunk          = dict(chunks[idx])
        chunk["score"] = round(score, 4)
        results.append(chunk)
    return results


def search_docs(query: str, season: str = None, entity: str = None) -> dict:
    """
    Agent-facing function. Returns {"chunks": [...], "result_count": N}.
    Each chunk has: text, source, page, season, score.
    Supports optional season and entity filtering.
    """
    try:
        raw = _hybrid_search(query, top_k=10)

        # Filter by season if provided
        if season:
            filtered = [c for c in raw if str(c.get("season", "")) == str(season)]
            raw = filtered if filtered else raw

        # Filter by entity if provided
        if entity:
            entity_lower = entity.lower()
            filtered = [c for c in raw if entity_lower in c.get("text", "").lower()]
            raw = filtered if filtered else raw

        chunks = raw[:5]

        return {
            "success":      True,
            "chunks":       chunks,
            "result_count": len(chunks),
            "query":        query,
        }

    except Exception as e:
        return {
            "success":      False,
            "chunks":       [],
            "result_count": 0,
            "query":        query,
            "error":        str(e),
        }


# ── CLI (unchanged) ───────────────────────────────────────────────────────────
def main():
    print("\n🏏 IPL RAG Search\n")
    while True:
        q = input("Query > ").strip()
        if q.lower() in ["exit", "quit"]:
            break
        results = search_docs(q)
        for i, r in enumerate(results["chunks"], 1):
            print(f"[{i}] {r['source']} | Page {r['page']} | Score: {r['score']}")
            print(r["text"][:200])
            print("-" * 60)


if __name__ == "__main__":
    main()