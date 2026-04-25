"""
utils/cache.py

Production-grade cache with:
- diskcache backend (persists between runs, thread-safe)
- Zone-aware TTL (Zone 3 / live questions expire in 1 hour, corpus questions never expire)
- Traceable cache logs (every hit/miss logged with zone and timestamp)
- Graceful fallback to JSON if diskcache not installed
"""

import hashlib
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("ipl.cache")

CACHE_DIR  = Path(__file__).resolve().parent.parent / "cache"
CACHE_LOG  = CACHE_DIR / "cache_log.jsonl"

# TTL in seconds
TTL_ZONE_3  = 60 * 60        # 1 hour  — live/current questions
TTL_ZONE_2  = 60 * 60 * 24  # 24 hours — corpus-present questions
TTL_ZONE_1  = None           # Never expires — historical facts don't change

# ── Try diskcache, fall back to plain JSON ────────────────────────────────────
try:
    import diskcache
    _dc = diskcache.Cache(str(CACHE_DIR / "dc"))
    _USE_DISKCACHE = True
except ImportError:
    _dc = None
    _USE_DISKCACHE = False


# ── Key ───────────────────────────────────────────────────────────────────────

def _key(question: str) -> str:
    return hashlib.md5(question.lower().strip().encode()).hexdigest()


# ── TTL selection ─────────────────────────────────────────────────────────────

def _ttl_for_zone(zone: int):
    """Return TTL seconds or None (never expires)."""
    if zone == 3:
        return TTL_ZONE_3
    if zone == 2:
        return TTL_ZONE_2
    return TTL_ZONE_1   # Zone 1 — historical, never expires


# ── Trace log ─────────────────────────────────────────────────────────────────

def _log(event: str, question: str, zone: int = None, ttl=None) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts":       time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event":    event,          # "HIT" | "MISS" | "SAVE" | "EXPIRE"
        "zone":     zone,
        "ttl_s":    ttl,
        "question": question[:120],
        "key":      _key(question),
    }
    with open(CACHE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Public API ────────────────────────────────────────────────────────────────

def load_cache(question: str, zone: int = 2):
    """
    Return cached answer dict if it exists and hasn't expired.
    zone is used to decide whether to honour TTL.
    Returns None on miss or expiry.
    """
    k = _key(question)

    if _USE_DISKCACHE:
        value = _dc.get(k)          # diskcache handles TTL automatically
        if value is not None:
            _log("HIT", question, zone)
            return value
        _log("MISS", question, zone)
        return None

    # ── JSON fallback ─────────────────────────────────────────────────────
    cache_file = CACHE_DIR / "answers.json"
    if not cache_file.exists():
        _log("MISS", question, zone)
        return None
    try:
        with open(cache_file, encoding="utf-8") as f:
            cache = json.load(f)
        entry = cache.get(k)
        if entry is None:
            _log("MISS", question, zone)
            return None

        # Check TTL manually for JSON backend
        ttl = _ttl_for_zone(zone)
        if ttl is not None:
            saved_at = entry.get("_cached_at", 0)
            if time.time() - saved_at > ttl:
                _log("EXPIRE", question, zone, ttl)
                return None

        _log("HIT", question, zone)
        return entry.get("_data", entry)   # unwrap if stored with metadata

    except (json.JSONDecodeError, OSError):
        _log("MISS", question, zone)
        return None


def save_cache(question: str, answer: dict, zone: int = 2) -> None:
    """
    Save answer to cache with zone-appropriate TTL.
    Zone 3 answers expire in 1 hour.
    Zone 1 answers never expire.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    k   = _key(question)
    ttl = _ttl_for_zone(zone)

    if _USE_DISKCACHE:
        _dc.set(k, answer, expire=ttl)   # None = never expires
        _log("SAVE", question, zone, ttl)
        return

    # ── JSON fallback ─────────────────────────────────────────────────────
    cache_file = CACHE_DIR / "answers.json"
    cache = {}
    if cache_file.exists():
        try:
            with open(cache_file, encoding="utf-8") as f:
                cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            cache = {}

    # Wrap with metadata so TTL can be checked on load
    cache[k] = {
        "_data":      answer,
        "_cached_at": time.time(),
        "_zone":      zone,
        "_ttl_s":     ttl,
        "_question":  question[:120],
    }

    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, default=str)

    _log("SAVE", question, zone, ttl)


def clear_cache() -> None:
    """Clear all cached answers."""
    if _USE_DISKCACHE:
        _dc.clear()
    cache_file = CACHE_DIR / "answers.json"
    if cache_file.exists():
        cache_file.unlink()
    print(f"[Cache] Cleared. Backend: {'diskcache' if _USE_DISKCACHE else 'JSON'}")


def cache_stats() -> dict:
    """Return cache statistics for telemetry."""
    if _USE_DISKCACHE:
        return {
            "backend":    "diskcache",
            "size":       len(_dc),
            "cache_dir":  str(CACHE_DIR / "dc"),
        }
    cache_file = CACHE_DIR / "answers.json"
    count = 0
    if cache_file.exists():
        try:
            with open(cache_file, encoding="utf-8") as f:
                count = len(json.load(f))
        except Exception:
            pass
    return {
        "backend":    "json_fallback",
        "size":       count,
        "cache_file": str(cache_file),
    }


def print_cache_log(tail: int = 20) -> None:
    """Print last N cache events for debugging."""
    if not CACHE_LOG.exists():
        print("No cache log yet.")
        return
    lines = CACHE_LOG.read_text(encoding="utf-8").strip().split("\n")
    for line in lines[-tail:]:
        try:
            e = json.loads(line)
            ttl_str = f"TTL={e['ttl_s']}s" if e.get("ttl_s") else "TTL=forever"
            print(f"[{e['ts']}] {e['event']:<7} Zone={e['zone']} {ttl_str} | {e['question'][:60]}")
        except Exception:
            print(line)