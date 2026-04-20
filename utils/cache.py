"""
utils/cache.py

File-based JSON cache. Persists between runs.
Zero API cost when the same question is asked again.
Key = MD5 hash of lowercased, stripped question.
"""

import json
import hashlib
import os
from pathlib import Path

CACHE_FILE = Path(__file__).resolve().parent.parent / "cache" / "answers.json"


def _hash(question: str) -> str:
    """Stable hash key from question text."""
    return hashlib.md5(question.lower().strip().encode()).hexdigest()


def load_cache(question: str):
    """Return cached answer dict if exists, else None."""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        return cache.get(_hash(question))
    except (json.JSONDecodeError, OSError):
        return None


def save_cache(question: str, answer: dict) -> None:
    """Save answer to cache file."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cache = {}
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE) as f:
                cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            cache = {}
    cache[_hash(question)] = answer
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, default=str)


def clear_cache() -> None:
    """Clear all cached answers (use during debugging)."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        print("Cache cleared.")