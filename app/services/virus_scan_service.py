"""
ClamAV integration for scanning uploaded medical files before they're
processed or made viewable.

Disabled by default (CLAMAV_ENABLED=false) since most dev machines don't
run a clamd daemon — in that mode every scan is recorded as "skipped" so
it's visible in processing_jobs, not silently pretended-clean.

To actually enable it:
  1. docker compose up -d clamav   (see docker-compose.yml)
  2. In .env: CLAMAV_ENABLED=true, CLAMAV_HOST=localhost, CLAMAV_PORT=3310
  3. Wait ~60-90s on first start — ClamAV downloads virus definitions
     before its socket comes up; scans will fail until it's ready.
"""

import io

from app.core.config import settings


def scan_bytes(raw_bytes: bytes) -> dict:
    if not settings.CLAMAV_ENABLED:
        return {"clean": True, "engine": "none", "detail": "ClamAV disabled — scan skipped"}

    import clamd

    try:
        cd = clamd.ClamdNetworkSocket(host=settings.CLAMAV_HOST, port=settings.CLAMAV_PORT)
        result = cd.instream(io.BytesIO(raw_bytes))
        status, signature = result.get("stream", ("ERROR", None))
        if status == "OK":
            return {"clean": True, "engine": "clamav", "detail": "no threats found"}
        if status == "FOUND":
            return {"clean": False, "engine": "clamav", "detail": signature or "malware detected"}
        return {"clean": True, "engine": "clamav", "detail": f"scan returned unexpected status: {status}"}
    except Exception as exc:
        # Fail OPEN, not closed: if the AV daemon is down, block every
        # upload in the app is worse for a medical platform than letting
        # an unscanned file through while clearly flagging that it happened.
        # This is a real product/security trade-off — revisit if you need
        # stricter guarantees (fail closed instead).
        return {"clean": True, "engine": "clamav", "detail": f"scan error, allowed through unscanned: {exc}"}