# Web API and dashboard

The Node service reads PostgreSQL, forwards live notifications and passes commands to the ingest
service. It writes nothing and holds no logic about the tank.

## API

| Route | Answer |
|---|---|
| `GET /api/definitions` | Parameters with units and limits (from ingest) |
| `GET /api/telemetry?seconds=120` | Recent points, 1 to 999 seconds |
| `GET /api/alarms` | Latest 20 alarms, active first |
| `GET /api/commands` | Latest 15 commands with their status |
| `GET /api/link` | Link counters |
| `POST /api/commands` | `{"name": ..., "args": {...}}`, limited to 30 per minute per address (`COMMANDS_PER_MINUTE`) |
| `GET /api/live` (WebSocket) | The `NOTIFY` messages described in [INGEST.md](INGEST.md) |

At most 100 live viewers; one that falls behind skips messages instead of queueing them.

There are **no user accounts**: anyone who can reach the page can command the simulated tank.
That is intentional for a demo with nothing real behind it.

## Dashboard

React and TypeScript, charts drawn with uPlot. It shows current values, two minutes of pressure and
temperature with their limit lines, active alarms, a command panel, command results and link
counters. It reconnects by itself and says when telemetry stops.

For development, with the rest running:

```bash
cd web/dashboard
npm ci
npm run dev
```

`npm run dev` expects the API on port 3000.
