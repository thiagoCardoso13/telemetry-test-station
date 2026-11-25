# Ingest service

The only process that talks to the equipment. It receives telemetry over UDP, stores it in
PostgreSQL, raises alarms and sends commands.

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/station python -m station.ingest
```

Defaults: telemetry on `127.0.0.1:5002`, commands to `127.0.0.1:5001`, one hour of history
(`--listen`, `--simulator`, `--keep-minutes`). `docker compose up` runs it for you.

## Commands

An internal HTTP interface (`--control`, default `127.0.0.1:5003`) is how the web API and the test
runner send commands:

| Request | Answer |
|---|---|
| `GET /definitions` | Parameters with limits, enums and functions |
| `POST /commands` with `{"name": "set_valve", "args": {"valve": "fill", "open": 1}}` | `202 {"id": 7}`, `400` if the command cannot be encoded, `503` if the database is away |

It has no authentication and is not published outside the containers.

## What gets stored

| Table | Content |
|---|---|
| `telemetry_sample` | One row per parameter per housekeeping report |
| `packet_log` | Events, command reports and rejected datagrams (not housekeeping: too frequent) |
| `command` | Each command and its status: sent, accepted, rejected, completed or failed |
| `alarm` | Parameter, bound (low or high), when raised and cleared |
| `link_counter` | Running totals about the link |

Rows older than the history window are deleted once a minute. See
[`schema.sql`](../station/src/station/ingest/schema.sql).

## Alarms

Limits come from [`definitions.yaml`](../station/src/station/protocol/definitions.yaml). An alarm is
raised after 3 consecutive readings outside a limit and cleared after 3 inside, so a single noisy
sample does neither. Alarms still open from a previous run are closed at start-up.

## Link problems

Nothing on the link stops the service; it counts instead.

| Counter | Meaning |
|---|---|
| `received` | Valid telemetry packets |
| `lost` | Gaps in the sequence count |
| `out_of_order` | Late or repeated packets, not stored |
| `resync` | The sender restarted (or 20 "old" packets in a row) |
| `rejected_<reason>` | See the reasons in [PROTOCOL.md](PROTOCOL.md) |
| `dropped` | Datagrams discarded because the queue was full |

A damaged packet usually counts twice: once as rejected and once as a gap in the sequence.

## Database outages

Datagrams wait in a queue of 1000 (about 100 seconds of telemetry) while the service retries the
same transaction. Beyond that, new datagrams are dropped and counted.

## Live data

Each committed batch is announced with PostgreSQL `NOTIFY` on the channel `station`, as JSON with
`"type"` equal to `telemetry`, `alarm` or `command`.

## Tests

The database tests need a PostgreSQL that may be wiped; without it they are skipped.

```bash
docker run --rm -d --name station-test-db -e POSTGRES_PASSWORD=test -p 127.0.0.1:55432:5432 postgres:17-alpine
TEST_DATABASE_URL=postgresql://postgres:test@127.0.0.1:55432/postgres pytest -q
```
