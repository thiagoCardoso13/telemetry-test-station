# Telemetry & Test Station

A small ground test station for a **simulated** pressurised tank: live telemetry, commands, alarms
and automated test sequences traced to requirements.

**Status:** the [link protocol](docs/PROTOCOL.md), [simulator](docs/SIMULATOR.md),
[ingest service](docs/INGEST.md), [live dashboard](docs/WEB.md) and
[test sequences](docs/TESTING.md) are done (phases 1 to 6 of the [project plan](docs/PLAN.md),
including end-to-end browser tests). A public demo comes next.

All data is synthetic. This project has no connection to real hardware.

## Run

```bash
docker compose up --build
```

Then open <http://localhost:3000>. Open the fill valve and watch the pressure rise; stick the relief
valve while filling to make the high-pressure alarm fire.

## Test sequences

With the station running:

```bash
docker compose run --rm runner
```

It prints each requirement as passed, failed, not run or not covered. See
[TESTING.md](docs/TESTING.md).

## Develop

Python (3.12):

```bash
cd station
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest -q
```

Web API and dashboard (Node 22), in `web/api` and again in `web/dashboard`:

```bash
cd web/api
npm ci
npm run typecheck && npm test && npm run build
```
