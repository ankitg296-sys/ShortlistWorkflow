"""P7: Monitoring, metrics, error tracking."""
import logging
import time
from functools import wraps
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class Metrics:
    """Simple in-memory metrics collection (production: use Prometheus/Datadog)."""

    def __init__(self):
        self.searches_started = 0
        self.searches_completed = 0
        self.searches_failed = 0
        self.scores_generated = 0
        self.scores_failed = 0
        self.search_durations = []

    def record_search_started(self):
        self.searches_started += 1

    def record_search_completed(self, duration_seconds: float):
        self.searches_completed += 1
        self.search_durations.append(duration_seconds)

    def record_search_failed(self):
        self.searches_failed += 1

    def record_score_generated(self):
        self.scores_generated += 1

    def record_score_failed(self):
        self.scores_failed += 1

    def get_avg_search_duration(self) -> float:
        if not self.search_durations:
            return 0.0
        return sum(self.search_durations) / len(self.search_durations)

    def snapshot(self) -> dict:
        """Return metrics snapshot."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "searches_started": self.searches_started,
            "searches_completed": self.searches_completed,
            "searches_failed": self.searches_failed,
            "avg_search_duration_seconds": self.get_avg_search_duration(),
            "scores_generated": self.scores_generated,
            "scores_failed": self.scores_failed,
            "error_rate": (
                self.searches_failed / self.searches_started
                if self.searches_started > 0
                else 0
            ),
        }


# Global metrics instance
metrics = Metrics()


def track_search(func):
    """Decorator to track search metrics."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        metrics.record_search_started()
        start = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start
            metrics.record_search_completed(duration)
            return result
        except Exception as e:
            metrics.record_search_failed()
            logger.error("search failed: %s", e)
            raise

    return wrapper


def log_with_redaction(message: str, **kwargs) -> str:
    """
    Log a message with sensitive data redacted.
    Redacts: api_key, encrypted_key, plaintext, sk-*, etc.
    """
    redacted = message
    for key, value in kwargs.items():
        if value and isinstance(value, str):
            if any(
                x in key.lower()
                for x in ["key", "secret", "plaintext", "token", "credential"]
            ):
                # Redact the value
                redacted = redacted.replace(value, f"<{key}-redacted>")
    return redacted


class SentryStub:
    """
    Sentry integration stub.
    In production, replace with: import sentry_sdk; sentry_sdk.init(dsn=...)
    """

    def __init__(self, dsn: str = None):
        self.dsn = dsn
        self.enabled = bool(dsn)

    def capture_exception(self, exc: Exception, context: dict = None):
        if self.enabled:
            logger.error(
                "sentry: %s (context: %s)",
                str(exc),
                log_with_redaction("", **context or {}),
            )

    def capture_message(self, message: str, level: str = "info"):
        if self.enabled:
            logger.log(getattr(logging, level.upper(), logging.INFO), message)


# Global sentry instance (disabled by default; enable via env var)
sentry = SentryStub()
