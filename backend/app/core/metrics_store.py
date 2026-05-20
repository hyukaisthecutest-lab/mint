from __future__ import annotations
import time
from collections import deque
from threading import Lock


class MetricsStore:
    """Sliding-window in-memory metrics for the real-time dashboard."""

    def __init__(self, window_seconds: int = 60) -> None:
        self._w = window_seconds
        self._lock = Lock()
        self._requests: deque[float] = deque()
        self._errors: deque[float] = deque()
        self._latencies: deque[tuple[float, float]] = deque()
        self._blocked: deque[float] = deque()
        self._active: int = 0
        self._tool_calls: dict[str, int] = {}
        self._tokens: dict[str, int] = {"prompt": 0, "completion": 0}

    def _prune(self, now: float) -> None:
        cutoff = now - self._w
        for q in (self._requests, self._errors, self._blocked):
            while q and q[0] < cutoff:
                q.popleft()
        while self._latencies and self._latencies[0][0] < cutoff:
            self._latencies.popleft()

    def request_start(self) -> None:
        with self._lock:
            now = time.time()
            self._requests.append(now)
            self._active += 1
            self._prune(now)

    def request_end(self, latency_ms: float, error: bool = False) -> None:
        with self._lock:
            now = time.time()
            self._latencies.append((now, latency_ms))
            if error:
                self._errors.append(now)
            self._active = max(0, self._active - 1)
            self._prune(now)

    def record_blocked(self) -> None:
        with self._lock:
            self._blocked.append(time.time())

    def record_tool(self, name: str) -> None:
        with self._lock:
            self._tool_calls[name] = self._tool_calls.get(name, 0) + 1

    def record_tokens(self, prompt: int, completion: int) -> None:
        with self._lock:
            self._tokens["prompt"] += prompt
            self._tokens["completion"] += completion

    def snapshot(self) -> dict:
        with self._lock:
            now = time.time()
            self._prune(now)
            lats = [ms for _, ms in self._latencies]
            sorted_lats = sorted(lats)
            n = len(sorted_lats)
            avg = round(sum(sorted_lats) / n) if n else 0
            p95 = round(sorted_lats[int(n * 0.95)]) if n >= 5 else avg
            p99 = round(sorted_lats[int(n * 0.99)]) if n >= 10 else avg
            req_count = len(self._requests)
            err_count = len(self._errors)
            scale = 60 / self._w
            return {
                "ts": round(now * 1000),
                "active": self._active,
                "req_per_min": round(req_count * scale, 1),
                "err_per_min": round(err_count * scale, 1),
                "error_rate_pct": round(err_count / max(req_count, 1) * 100, 1),
                "latency": {"avg": avg, "p95": p95, "p99": p99},
                "blocked_per_min": round(len(self._blocked) * scale, 1),
                "tool_calls": dict(self._tool_calls),
                "tokens": dict(self._tokens),
            }


store = MetricsStore()
