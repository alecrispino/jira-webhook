"""Header-basierte Authentifizierung.

Zwei getrennte Credentials (Least Privilege): Wer Webhooks schicken darf,
kann keine Statistiken lesen, und umgekehrt.
"""

import secrets
from typing import Callable, Optional

from fastapi import Header, HTTPException, Request, status

from app.config import Settings


def _matches(provided: Optional[str], expected: str) -> bool:
    if not provided:
        return False
    # Zeitkonstanter Vergleich. Auf Bytes, weil compare_digest bei str nur
    # ASCII akzeptiert und sonst eine TypeError (-> 500) werfen würde.
    return secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def require_webhook_secret(
    request: Request,
    x_webhook_secret: Optional[str] = Header(default=None),
) -> None:
    if not _matches(x_webhook_secret, _settings(request).webhook_secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


def require_stats_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
) -> None:
    if not _matches(x_api_key, _settings(request).stats_api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
