# Telemetry & Test Station

A small ground test station for a **simulated** pressurised tank: live telemetry, commands, alarms
and automated test sequences traced to requirements.

**Status:** the [link protocol](docs/PROTOCOL.md), the [simulator](docs/SIMULATOR.md) and the
[ingest service](docs/INGEST.md) are done (phases 1 to 3 of the [project plan](docs/PLAN.md)).
The dashboard comes next; until then the data is only visible in the database.

All data is synthetic. This project has no connection to real hardware.

## Run

```bash
docker compose up --build
```

This starts PostgreSQL, the simulator, the ingest service and the web API
(<http://localhost:3000/health>). To see telemetry arriving:

```bash
docker compose exec db psql -U station -d station -c "SELECT * FROM telemetry_sample ORDER BY time DESC LIMIT 5"
```

## Develop

Python (3.12):

```bash
cd station
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest -q
```

Web API (Node 22):

```bash
cd web/api
npm ci
npm run typecheck && npm test
```
