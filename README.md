# Jira Webhook Service

Empfängt Webhooks aus der Jira Automation („Send web request“), speichert jedes Event
append-only als Audit-Log und den aktuellen Stand pro Issue in SQLite.

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Starten

```sh
export WEBHOOK_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export STATS_API_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
uvicorn --factory app.main:create_app --host 0.0.0.0 --port 8000
```

Ohne `WEBHOOK_SECRET` oder `STATS_API_KEY` startet der Service nicht.

## Docker

```sh
docker build -t jira-webhook .
docker run -d --name jira-webhook -p 8000:8000 \
  --env-file .env \
  -v jira-webhook-data:/data \
  jira-webhook
```

Die SQLite-Datei liegt im Volume unter `/data/jira.db` und überlebt Neustarts und Updates des Containers.

## Jira Automation konfigurieren

Aktion **Send web request**:

- URL: `https://<host>/webhook/jira`
- Methode: `POST`
- Header: `X-Webhook-Secret: <WEBHOOK_SECRET>` (in Jira als *hidden* markieren)
- Body (Custom data):

```json
{
  "key": "{{issue.key}}",
  "summary": {{issue.summary.asJsonString}},
  "status": "{{issue.status.name}}",
  "urgency": "{{issue.Urgency.value}}"
}
```

`asJsonString` escaped Anführungszeichen in der Summary. Eine leere Urgency (`""`) wird als `null` gespeichert.

## Endpunkte

| Methode | Pfad            | Header             | Zweck                                          |
|---------|-----------------|--------------------|------------------------------------------------|
| POST    | `/webhook/jira` | `X-Webhook-Secret` | Event speichern (Audit-Log + Upsert in issues) |
| GET     | `/stats`        | `X-API-Key`        | Anzahl Issues pro Status und Urgency           |

```sh
curl -X POST localhost:8000/webhook/jira \
  -H "X-Webhook-Secret: $WEBHOOK_SECRET" -H "Content-Type: application/json" \
  -d '{"key":"OPS-1","summary":"Server down","status":"To Do","urgency":"High"}'

curl localhost:8000/stats -H "X-API-Key: $STATS_API_KEY"
```

## Tests

```sh
pytest
```
