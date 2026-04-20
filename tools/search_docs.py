"""
search_docs.py
--------------
Hybrid Reciprocal Rank Fusion (BM25 + FAISS) retrieval over the
pre-built index.  Run standalone to smoke-test the index.

Usage:
    python tools/search_docs.py                  # runs built-in test queries
    python tools/search_docs.py "your question"  # single ad-hoc query
"""

import json
import pickle
import re
import sys
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent.parent
INDEX_DIR = BASE_DIR / "data" / "index"

# ── Embedding model (must match ingest_docs.py) ───────────────────────────────
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


# ── Helpers ───────────────────────────────────────────────────────────────────
def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _index_ready() -> bool:
    needed = [
        INDEX_DIR / "faiss.index",
        INDEX_DIR / "chunks.json",
        INDEX_DIR / "bm25.pkl",
    ]
    return all(p.exists() for p in needed)


def load_index() -> tuple:
    if not _index_ready():
        raise FileNotFoundError(
            f"Index not found in {INDEX_DIR}. "
            "Run  python ingest/ingest_docs.py  first."
        )

    faiss_index = faiss.read_index(str(INDEX_DIR / "faiss.index"))

    with open(INDEX_DIR / "chunks.json", encoding="utf-8") as f:
        chunks = json.load(f)

    with open(INDEX_DIR / "bm25.pkl", "rb") as f:
        bm25 = pickle.load(f)

    return faiss_index, chunks, bm25


# ── Core search ───────────────────────────────────────────────────────────────
def search(
    query: str,
    top_k: int    = 3,
    bm25_k: int   = 15,
    faiss_k: int  = 15,
    rrf_k: int    = 60,       # RRF smoothing constant (standard = 60)
) -> list[dict]:
    """
    Hybrid Reciprocal Rank Fusion:
      score(doc) = Σ  1 / (rrf_k + rank_in_list)
    over the BM25 top-k and FAISS top-k lists.

    Returns a list of dicts:  {"text": ..., "source": ..., "score": ...}
    """
    faiss_index, chunks, bm25 = load_index()
    model = _get_model()

    # ── BM25 ranking ────────────────────────────────────────────────────────
    bm25_scores = bm25.get_scores(tokenize(query))
    bm25_top    = np.argsort(bm25_scores)[::-1][:bm25_k].tolist()

    # ── FAISS ranking ────────────────────────────────────────────────────────
    q_emb = model.encode([query])
    q_emb = np.array(q_emb, dtype="float32")
    faiss.normalize_L2(q_emb)
    _, faiss_hits = faiss_index.search(q_emb, faiss_k)
    faiss_top     = faiss_hits[0].tolist()

    # ── Reciprocal Rank Fusion ───────────────────────────────────────────────
    rrf_scores: dict[int, float] = {}

    for rank, idx in enumerate(bm25_top):
        rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (rrf_k + rank + 1)

    for rank, idx in enumerate(faiss_top):
        rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (rrf_k + rank + 1)

    # ── Build result list ────────────────────────────────────────────────────
    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    results = []
    for idx, score in ranked:
        chunk = chunks[idx]
        results.append({
            "text":   chunk["text"],
            "source": chunk["source"],
            "score":  round(score, 5),
        })

    return results


# ── Pretty printer ────────────────────────────────────────────────────────────
def print_results(query: str, results: list[dict], preview: int = 300) -> None:
    print(f"\n{'─'*60}")
    print(f"Query : {query}")
    print(f"{'─'*60}")

    if not results:
        print("  (no results)")
        return

    for i, r in enumerate(results, start=1):
        snippet = r["text"][:preview].replace("\n", " ")
        if len(r["text"]) > preview:
            snippet += "…"
        print(f"\n  [{i}] {r['source']}  (score={r['score']})")
        print(f"      {snippet}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # If a CLI argument is given, run that single query; otherwise run defaults.
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print_results(q, search(q))
    else:
        test_queries = [
            "IPL 2023 winner",
            "IPL 2022 winner",
            "top run scorer 2023",
            "final match details",
            "player of the match final",
            "highest score in IPL 2023",
        ]

        print("\n" + "=" * 60)
        print("Smoke-testing retrieval")
        print("=" * 60)

        for q in test_queries:
            print_results(q, search(q))

        print(f"\n{'='*60}")
        print("Done.")