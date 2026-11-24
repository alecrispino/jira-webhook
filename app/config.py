"""Konfiguration aus Umgebungsvariablen.

Fehlende Secrets führen zum Abbruch beim Start (fail fast): Ein Service, der
versehentlich ohne Secret läuft und alles annimmt, ist schlimmer als einer,
der gar nicht startet.
"""

import os
from dataclasses import dataclass
from typing import Mapping, Optional


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    webhook_secret: str
    stats_api_key: str
    db_path: str = "jira.db"

    def __repr__(self) -> str:  # Secrets nie in Logs/Tracebacks ausgeben
        return f"Settings(webhook_secret=***, stats_api_key=***, db_path={self.db_path!r})"


def _require(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"Umgebungsvariable {name} fehlt oder ist leer.")
    return value


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    env = os.environ if env is None else env
    settings = Settings(
        webhook_secret=_require(env, "WEBHOOK_SECRET"),
        stats_api_key=_require(env, "STATS_API_KEY"),
        db_path=env.get("DB_PATH", "").strip() or "jira.db",
    )
    if settings.webhook_secret == settings.stats_api_key:
        raise ConfigError("WEBHOOK_SECRET und STATS_API_KEY müssen verschieden sein.")
    return settings
