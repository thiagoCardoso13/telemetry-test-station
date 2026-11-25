# Telemetry & Test Station — Project Plan

Working name: `telemetry-test-station`.

## 1. Problem

Before hardware flies, it is tested on a bench: sensors send telemetry, operators watch it live, send
commands, run test procedures and prove that every requirement was verified. This project builds a
small, complete version of that loop around a **simulated** pressurised tank.

## 2. What a visitor can do

1. Watch tank pressure, temperature and valve states update live.
2. Send a command (open or close a valve) and see the acknowledgement and the effect.
3. Inject a fault (leak, stuck valve, noisy sensor) and watch the alarm fire.
4. Run a test sequence and read a pass/fail report traced to requirements.

## 3. Scope

**In:** simulator, packet protocol, ingest service, database, live dashboard, commands, alarms,
test sequences, traceability report, CI, public demo.

**Out:** real hardware, user accounts, multiple vehicles, full CCSDS/ECSS compliance.

All data is synthetic. The protocol is *inspired by* CCSDS Space Packets and ECSS PUS and implements
only a documented subset. No company name or branding appears in the repository.

## 4. Architecture

```
 simulator (Python) --UDP telemetry--> ingest (Python) --> PostgreSQL
        ^                                   |                  ^
        +----------UDP telecommands---------+                  |
                                            ^                  |
 test runner (Python) ----------------------+------------------+
                                            |
 browser (React) <--WebSocket/REST--> web API (Node + TypeScript)
```

- The ingest service is the only process that talks to the simulator.
- Commands: web API and test runner call the ingest service, which encodes and sends them.
- Live data: the ingest service uses PostgreSQL `LISTEN/NOTIFY`; the web API forwards to browsers.

## 5. Stack

| Part | Choice |
|---|---|
| Simulator, ingest, test runner | Python 3.12, asyncio, pytest, ruff |
| Database | PostgreSQL |
| Web API | Node 22, TypeScript, Fastify, WebSocket |
| Dashboard | React, TypeScript, Vite, a charting library chosen in phase 4 |
| Tests | pytest, Vitest, Playwright |
| Delivery | Docker Compose (Linux containers), GitHub Actions |
| Demo | Free tiers only: Render web service + Neon PostgreSQL |

## 6. Protocol (subset)

Packet = 6-byte CCSDS-style primary header + short secondary header (service, subservice, timestamp)
+ payload + CRC-16.

| Service | Use |
|---|---|
| 1 | Command acceptance and completion reports |
| 3 | Periodic housekeeping telemetry |
| 5 | Events and alarms raised by the simulator |
| 8 | Commands (valves, fault injection) |
| 17 | Connection test (ping) |

Parameters (name, type, unit, limits) live in one YAML file that both encoder and decoder read.
Exact byte layouts go in `docs/PROTOCOL.md` in phase 1.

## 7. Data model

- `telemetry_sample(time, parameter, value)` — indexed by parameter and time, pruned by age
- `packet_log(time, direction, service, subservice, sequence, valid)`
- `command(id, sent_at, name, args, status)`
- `alarm(id, parameter, raised_at, cleared_at, severity)`
- `test_run(id, sequence, started_at, finished_at, result)`
- `test_step(run_id, index, requirement_id, expected, observed, passed)`

## 8. Test sequences and traceability

Requirements live in `requirements.yaml` (`REQ-001`: "The relief valve opens when pressure exceeds
X bar within 500 ms"). Sequences are YAML files with steps: `command`, `wait_for`, `check`,
`inject_fault`. Every `check` names a requirement. The report (HTML) shows each requirement as
passed, failed or **not covered**.

## 9. Phases

Estimate: about 4 weeks part-time. Each phase ends with tests passing and a commit.

| # | Phase | Done when | Estimate |
|---|---|---|---|
| 0 | Skeleton: repo layout, Docker Compose, CI | CI green on an empty test suite for Python and Node | 1 day |
| 1 | Protocol: encode/decode, CRC, `PROTOCOL.md` | Round-trip and corrupted-packet tests pass | 3 days |
| 2 | Simulator: tank physics, faults, commands | A command visibly changes pressure; faults are reproducible with a seed | 3 days |
| 3 | Ingest + database + alarms | Telemetry stored; packet loss and bad CRC are counted, not fatal | 3 days |
| 4 | Web API + live dashboard | Live charts, command panel, alarm list | 5 days |
| 5 | Test runner + traceability report | At least 8 requirements, 4 sequences, one sequence that fails on an injected fault | 4 days |
| 6 | End-to-end tests | Playwright covers command → telemetry → alarm; runs in CI | 2 days |
| 7 | Deploy + showcase | Public demo, README with diagram and GIF | 3 days |

**Checkpoint after phase 5:** if time is short, skip phase 6 and ship.

**Optional phase 8:** a simulated power supply that speaks SCPI over TCP, driven by test sequences.

## 10. Public demo constraints

- One container runs simulator, ingest and web API, so UDP stays on localhost.
- Free services sleep when idle: the dashboard must show a "waking up" state.
- The simulation is shared by all visitors: rate-limit commands and offer a reset button.
- Keep little history so the free database does not fill up.
- Check current free-tier limits at the start of phase 7. The Space Booking API already uses these
  providers, so confirm both fit.

## 11. Risks

| Risk | Response |
|---|---|
| Scope is large for one person | Phases 1–5 already tell the whole story; 6 and 8 are cuttable |
| React and Node are less familiar than Python and Java | Keep the web API thin; no logic that belongs in ingest |
| Looks like a toy | Document the protocol, measure latency and packet rate, show a failing test |
| Claims beyond what was built | README says "subset, inspired by", never "compliant" |

## 12. Success criteria

- `docker compose up` runs everything on a clean machine.
- A visitor understands the project in one minute from the README GIF.
- README reports measured numbers: telemetry rate, end-to-end latency, test count.
- The author can explain every part in an interview.
