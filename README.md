# Telemetry & Test Station

A small ground test station for a **simulated** pressurised tank: live telemetry, commands, alarms
and automated test sequences traced to requirements.

**Status:** the [link protocol](docs/PROTOCOL.md) and the [simulator](docs/SIMULATOR.md) are done
(phases 1 and 2 of the [project plan](docs/PLAN.md)). Receiving and storing telemetry comes next.

All data is synthetic. This project has no connection to real hardware.

## Run

```bash
docker compose up --build
```

The web API answers on <http://localhost:3000/health>.

## Simulator

After installing the Python package (below):

```bash
python -m station.simulator --seed 1
```

It sends binary telemetry over UDP; nothing displays it yet.

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
