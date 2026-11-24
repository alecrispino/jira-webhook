import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

WEBHOOK_SECRET = "test-webhook-secret"
STATS_API_KEY = "test-stats-key"


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def client(db_path):
    settings = Settings(webhook_secret=WEBHOOK_SECRET, stats_api_key=STATS_API_KEY, db_path=db_path)
    with TestClient(create_app(settings)) as c:  # `with` löst den Lifespan (init_db) aus
        yield c


@pytest.fixture
def webhook_headers():
    return {"X-Webhook-Secret": WEBHOOK_SECRET}


@pytest.fixture
def stats_headers():
    return {"X-API-Key": STATS_API_KEY}
