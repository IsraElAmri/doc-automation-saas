"""
In-memory thread-safe metrics store for per-route request tracking.

Known limitation: metrics reset to zero on every server restart/redeploy
and are not consistent across multiple worker processes. Acceptable at
single-worker scale; would need Redis or a DB-backed store to survive restarts
or scale horizontally.
"""
import re
import threading
from datetime import datetime, timezone
from typing import Dict


_lock = threading.Lock()

# Route normalization patterns: collapse path IDs to their parameter names
_PARAM_PATTERNS = [
    (re.compile(r"/ask/\d+"), "/ask/{document_id}"),
    (re.compile(r"/extract/\d+"), "/extract/{document_id}"),
    (re.compile(r"/chat-history/\d+"), "/chat-history/{document_id}"),
    (re.compile(r"/documents/\d+"), "/documents/{document_id}"),
]

# Store shape: { "METHOD /route": {"requests": int, "4xx": int, "5xx": int, "total_ms": float} }
_store: Dict[str, Dict] = {}


def _normalize_route(method: str, path: str) -> str:
    for pattern, replacement in _PARAM_PATTERNS:
        path = pattern.sub(replacement, path)
    return f"{method} {path}"


def record(method: str, path: str, status_code: int, duration_ms: float) -> None:
    """Record one request into the metrics store. Thread-safe."""
    key = _normalize_route(method, path)
    with _lock:
        if key not in _store:
            _store[key] = {"requests": 0, "4xx": 0, "5xx": 0, "total_ms": 0.0}
        entry = _store[key]
        entry["requests"] += 1
        entry["total_ms"] += duration_ms
        if 400 <= status_code < 500:
            entry["4xx"] += 1
        elif status_code >= 500:
            entry["5xx"] += 1


def snapshot() -> dict:
    """Return a point-in-time snapshot of all metrics."""
    with _lock:
        routes = {}
        total_requests = 0
        total_4xx = 0
        total_5xx = 0
        total_ms = 0.0

        for key, entry in sorted(_store.items()):
            reqs = entry["requests"]
            fxx = entry["4xx"]
            svx = entry["5xx"]
            ms = entry["total_ms"]
            avg_ms = round(ms / reqs, 2) if reqs > 0 else 0.0
            error_pct = round(((fxx + svx) / reqs) * 100, 2) if reqs > 0 else 0.0

            routes[key] = {
                "requests": reqs,
                "4xx": fxx,
                "5xx": svx,
                "avg_latency_ms": avg_ms,
                "error_rate_pct": error_pct,
            }
            total_requests += reqs
            total_4xx += fxx
            total_5xx += svx
            total_ms += ms

        total_avg_ms = round(total_ms / total_requests, 2) if total_requests > 0 else 0.0
        total_error_pct = round(((total_4xx + total_5xx) / total_requests) * 100, 2) if total_requests > 0 else 0.0

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "routes": routes,
            "totals": {
                "requests": total_requests,
                "4xx": total_4xx,
                "5xx": total_5xx,
                "avg_latency_ms": total_avg_ms,
                "error_rate_pct": total_error_pct,
            },
        }


def reset() -> None:
    """Clear all metrics. Used in tests."""
    with _lock:
        _store.clear()
