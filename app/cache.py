from datetime import datetime, timezone
from threading import RLock
import time
from typing import Any, Dict, Optional, Tuple

DEFAULT_TTL_SECONDS = 900  # 15 minutes

_lock = RLock()
_cache: Dict[str, Tuple[float, Any]] = {}
_version: int = 0
_next_deadline: Optional[datetime] = None


def get_cached(key: str) -> Tuple[bool, Any, int]:
    """
    Look up `key` in the in-memory TTL cache.
    Returns `(hit, value, current_version)`.
    """
    now_mono = time.monotonic()
    with _lock:
        entry = _cache.get(key)
        if entry is not None:
            expires_at, value = entry
            if now_mono < expires_at:
                return True, value, _version
            _cache.pop(key, None)
        return False, None, _version


def set_cached(
    key: str,
    value: Any,
    expected_version: int,
    ttl: int = DEFAULT_TTL_SECONDS,
) -> bool:
    """
    Store `value` under `key` only if no invalidation occurred since `expected_version`.
    Returns True if stored, False if skipped due to concurrent invalidation.
    """
    expires_at = time.monotonic() + ttl
    with _lock:
        if expected_version != _version:
            return False
        _cache[key] = (expires_at, value)
        return True


def invalidate(*keys: str) -> None:
    """Invalidate specific cache keys and bump cache version."""
    with _lock:
        global _version
        _version += 1
        for k in keys:
            _cache.pop(k, None)


def invalidate_prefix(*prefixes: str) -> None:
    """Invalidate all cache keys matching any of the given prefixes and bump cache version."""
    with _lock:
        global _version
        _version += 1
        to_remove = [k for k in _cache if k.startswith(prefixes)]
        for k in to_remove:
            _cache.pop(k, None)


def clear_all_cache() -> None:
    """Clear the entire cache and bump cache version."""
    with _lock:
        global _version
        _version += 1
        _cache.clear()


def set_next_deadline(dt: Optional[datetime]) -> None:
    """Set the next UTC deadline timestamp that can trigger a state transition."""
    with _lock:
        global _next_deadline
        if dt is not None and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        elif dt is not None:
            dt = dt.astimezone(timezone.utc)
        _next_deadline = dt


def get_next_deadline() -> Optional[datetime]:
    """Return the currently tracked UTC deadline, if any."""
    with _lock:
        return _next_deadline


def is_deadline_passed() -> bool:
    """Pure in-memory check (0 DB queries) for whether the next tracked deadline has passed."""
    with _lock:
        if _next_deadline is None:
            return False
        return datetime.now(timezone.utc) > _next_deadline
