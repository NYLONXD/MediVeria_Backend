"""
Thin Redis wrapper for a short-lived, single-use "card verified" flag.
Reuses REDIS_URL (already configured for Celery) — no new infra.
"""

import redis

from app.core.config import settings

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

_PREFIX = "card_verified:"


def mark_card_verified(user_id) -> None:
    """Set right after a doctor re-taps their card for a sensitive action.
    TTL is just a safety net if the flag is never consumed."""
    redis_client.setex(f"{_PREFIX}{user_id}", settings.CARD_VERIFY_TTL_SECONDS, "1")


def consume_card_verification(user_id) -> bool:
    """Check-and-delete atomically — one verified tap is good for exactly
    one action (one upload, one delete), never more."""
    key = f"{_PREFIX}{user_id}"
    pipe = redis_client.pipeline()
    pipe.get(key)
    pipe.delete(key)
    value, _ = pipe.execute()
    return value == "1"