# Telemetry & Test Station

A small ground test station for a **simulated** pressurised tank: live telemetry, commands, alarms
and automated test sequences traced to requirements.

**Status:** skeleton (phase 0). See the [project plan](docs/PLAN.md).

All data is synthetic. This project has no connection to real hardware.

## Run

```bash
docker compose up --build
```

The web API answers on <http://localhost:3000/health>.

## Develop

Python (3.12):

```bash
cd station
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check . && pytest -q
```

Web API (Node 22):

```bash
cd web/api
npm ci
npm run typecheck && npm test
```
