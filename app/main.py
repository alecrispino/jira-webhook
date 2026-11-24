"""FastAPI-App.

Start:  uvicorn --factory app.main:create_app
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, Request
from starlette.concurrency import run_in_threadpool

from app import db
from app.auth import require_stats_api_key, require_webhook_secret
from app.config import Settings, load_settings
from app.schemas import JiraEvent, StatsResponse, WebhookResponse


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    # Settings werden beim Erzeugen der App geladen -> fehlende Secrets brechen den Start ab.
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.init_db(settings.db_path)
        yield

    app = FastAPI(title="Jira Webhook Service", lifespan=lifespan)
    app.state.settings = settings

    @app.post(
        "/webhook/jira",
        response_model=WebhookResponse,
        dependencies=[Depends(require_webhook_secret)],
    )
    async def jira_webhook(event: JiraEvent, request: Request) -> WebhookResponse:
        # FastAPI hat den Body für die Validierung bereits gelesen; request.body()
        # liefert dieselben, gecachten Bytes. So landet das Original im Audit-Log,
        # nicht eine re-serialisierte (und um Extra-Felder gekürzte) Version.
        raw = (await request.body()).decode("utf-8")
        # sqlite3 blockiert -> im Threadpool ausführen, damit die Event-Loop frei bleibt.
        event_id = await run_in_threadpool(db.record_event, settings.db_path, raw, event)
        return WebhookResponse(status="stored", event_id=event_id)

    @app.get(
        "/stats",
        response_model=StatsResponse,
        dependencies=[Depends(require_stats_api_key)],
    )
    def stats() -> StatsResponse:
        # Sync-Endpunkt: FastAPI führt ihn automatisch im Threadpool aus.
        return StatsResponse(**db.get_stats(settings.db_path))

    return app
