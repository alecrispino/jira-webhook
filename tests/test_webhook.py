import json
import sqlite3

import pytest

from tests.conftest import STATS_API_KEY

EVENT = {"key": "OPS-1", "summary": "Server down", "status": "To Do", "urgency": "High"}


def rows(db_path, sql):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Webhook-Secret": "wrong"},
        {"X-Webhook-Secret": ""},
        {"X-Webhook-Secret": "wröng".encode("utf-8")},  # Nicht-ASCII darf keinen 500er auslösen
        {"X-API-Key": STATS_API_KEY},  # Stats-Key darf keine Webhooks schreiben
        {"X-Webhook-Secret": STATS_API_KEY},
    ],
)
def test_rejects_invalid_secret(client, db_path, headers):
    r = client.post("/webhook/jira", json=EVENT, headers=headers)
    assert r.status_code == 401
    assert rows(db_path, "SELECT COUNT(*) FROM jira_events") == [(0,)]


def test_stores_event_and_issue(client, db_path, webhook_headers):
    r = client.post("/webhook/jira", json=EVENT, headers=webhook_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "stored"

    assert rows(db_path, "SELECT key, summary, status, urgency FROM issues") == [
        ("OPS-1", "Server down", "To Do", "High")
    ]
    [(payload,)] = rows(db_path, "SELECT payload FROM jira_events")
    assert json.loads(payload) == EVENT


def test_raw_payload_is_stored_verbatim(client, db_path, webhook_headers):
    body = '{"key":"OPS-9","summary":"x","status":"Done","urgency":"Low","extra":{"a":1}}'
    r = client.post(
        "/webhook/jira",
        content=body,
        headers={**webhook_headers, "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert rows(db_path, "SELECT payload FROM jira_events") == [(body,)]


def test_second_event_upserts_issue_but_appends_event(client, db_path, webhook_headers):
    client.post("/webhook/jira", json=EVENT, headers=webhook_headers)
    client.post("/webhook/jira", json={**EVENT, "status": "Done"}, headers=webhook_headers)

    assert rows(db_path, "SELECT key, status FROM issues") == [("OPS-1", "Done")]
    assert rows(db_path, "SELECT COUNT(*) FROM jira_events") == [(2,)]


@pytest.mark.parametrize("urgency", [None, "", "   "])
def test_missing_urgency_is_null(client, db_path, webhook_headers, urgency):
    client.post("/webhook/jira", json={**EVENT, "urgency": urgency}, headers=webhook_headers)
    assert rows(db_path, "SELECT urgency FROM issues") == [(None,)]


@pytest.mark.parametrize(
    "body",
    [
        {"summary": "no key", "status": "To Do"},
        {"key": "", "summary": "x", "status": "To Do"},
        {"key": "OPS-1", "summary": "x"},
    ],
)
def test_invalid_payload_is_rejected(client, db_path, webhook_headers, body):
    r = client.post("/webhook/jira", json=body, headers=webhook_headers)
    assert r.status_code == 422
    assert rows(db_path, "SELECT COUNT(*) FROM jira_events") == [(0,)]


def test_events_table_is_append_only(client, db_path, webhook_headers):
    client.post("/webhook/jira", json=EVENT, headers=webhook_headers)
    conn = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE jira_events SET payload = '{}'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM jira_events")
    finally:
        conn.close()


def test_malformed_json_is_rejected(client, db_path, webhook_headers):
    r = client.post(
        "/webhook/jira",
        content='{"key": "OPS-1", "summary": ',
        headers={**webhook_headers, "Content-Type": "application/json"},
    )
    assert r.status_code == 422
    assert rows(db_path, "SELECT COUNT(*) FROM jira_events") == [(0,)]


def test_auth_is_checked_before_payload(client, db_path):
    # Ohne Secret gibt es 401, nicht 422: Unauthentifizierte erfahren nichts über das Schema.
    r = client.post("/webhook/jira", json={"garbage": True})
    assert r.status_code == 401


def test_summary_with_quotes_and_unicode(client, db_path, webhook_headers):
    summary = 'Login "SSO" kaputt – Ärger mit 🔥'
    client.post("/webhook/jira", json={**EVENT, "summary": summary}, headers=webhook_headers)
    assert rows(db_path, "SELECT summary FROM issues") == [(summary,)]


def test_whitespace_in_key_does_not_create_duplicate(client, db_path, webhook_headers):
    client.post("/webhook/jira", json=EVENT, headers=webhook_headers)
    client.post("/webhook/jira", json={**EVENT, "key": "  OPS-1 "}, headers=webhook_headers)
    assert rows(db_path, "SELECT key FROM issues") == [("OPS-1",)]


def test_event_ids_increase_and_timestamps_are_utc(client, db_path, webhook_headers):
    ids = [
        client.post("/webhook/jira", json=EVENT, headers=webhook_headers).json()["event_id"]
        for _ in range(3)
    ]
    assert ids == sorted(ids) and len(set(ids)) == 3
    for (received_at,) in rows(db_path, "SELECT received_at FROM jira_events"):
        assert received_at.endswith("+00:00")
