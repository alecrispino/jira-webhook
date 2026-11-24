import pytest

from app.config import ConfigError, load_settings
from tests.conftest import WEBHOOK_SECRET


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-API-Key": "wrong"}, {"X-API-Key": WEBHOOK_SECRET}, {"X-Webhook-Secret": WEBHOOK_SECRET}],
)
def test_stats_requires_api_key(client, headers):
    assert client.get("/stats", headers=headers).status_code == 401


def test_stats_empty(client, stats_headers):
    r = client.get("/stats", headers=stats_headers)
    assert r.status_code == 200
    assert r.json() == {"by_status": {}, "by_urgency": {}}


def test_stats_counts_current_state(client, webhook_headers, stats_headers):
    events = [
        {"key": "OPS-1", "summary": "a", "status": "To Do", "urgency": "High"},
        {"key": "OPS-2", "summary": "b", "status": "To Do", "urgency": "Low"},
        {"key": "OPS-3", "summary": "c", "status": "Done", "urgency": None},
        # OPS-1 wechselt den Status: zählt danach nur noch als "Done"
        {"key": "OPS-1", "summary": "a", "status": "Done", "urgency": "High"},
    ]
    for e in events:
        assert client.post("/webhook/jira", json=e, headers=webhook_headers).status_code == 200

    r = client.get("/stats", headers=stats_headers)
    assert r.json() == {
        "by_status": {"Done": 2, "To Do": 1},
        "by_urgency": {"High": 1, "Low": 1, "none": 1},
    }


def test_config_fails_fast_without_secrets():
    with pytest.raises(ConfigError, match="WEBHOOK_SECRET"):
        load_settings({"STATS_API_KEY": "k"})
    with pytest.raises(ConfigError, match="STATS_API_KEY"):
        load_settings({"WEBHOOK_SECRET": "s"})


def test_config_rejects_identical_secrets():
    with pytest.raises(ConfigError, match="verschieden"):
        load_settings({"WEBHOOK_SECRET": "same", "STATS_API_KEY": "same"})
