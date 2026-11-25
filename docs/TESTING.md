# Test sequences and traceability

The runner executes test sequences against the tank and reports one verdict per requirement.

```bash
python -m station.runner --report report/report.html     # in-process simulation, under a second
docker compose run --rm runner                           # the running station, about 45 s
```

`--include-faults` adds the sequences that break the tank on purpose; they are meant to fail.
Exit code: `0` all passed, `1` something failed, `2` the bench did not work (no verdict).

## Two benches, one set of sequences

| Bench | What it exercises | Time |
|---|---|---|
| In-process | Simulator, protocol and ingest processing | Simulated: fast and repeatable |
| `--live` | The same, plus UDP, the ingest service, the database and its control interface | Real |

Neither goes through the web API or the dashboard. A live run resets the shared tank, so anyone
watching the dashboard will see it, and someone else sending commands can spoil the result.

## Writing a sequence

Requirements are in [`requirements.yaml`](../station/src/station/runner/suite/requirements.yaml),
sequences in [`suite/`](../station/src/station/runner/suite). Every sequence starts from a reset tank.

| Step | Meaning |
|---|---|
| `command` + `args`, `expect` | Send a command; expect `completed` (default), `failed` or `rejected` |
| `inject_fault` | Shorthand for the fault command |
| `wait` | Let time pass |
| `wait_for` + `timeout` | Until a condition holds |
| `check` | The condition holds now |
| `always` + `for` | The condition holds on every sample for that long |
| `response`: `when`, `then`, `within`, `after` | After the first `when` since the start (and after `after`), `then` follows in time |

Conditions are `parameter <op> number`, `alarm <parameter> <low|high>` or `no alarm ...`.
A step with `requirement:` counts as evidence for it. A failed `command` or `wait_for` stops the
sequence and the remaining steps are reported as `not run`. Mistakes in the YAML are refused before
anything runs.

## Verdicts

| Verdict | Meaning |
|---|---|
| passed | Every step that verifies it passed |
| failed | At least one failed |
| not run | None failed, but some could not run |
| not covered | No sequence in this run verifies it |

Two requirements are **not covered** by the normal run, on purpose and visibly:

- **REQ-007** (high pressure alarm): the relief valve prevents high pressure, so it is only verified
  by the fault demonstration.
- **REQ-011** (implausible sensor): the station has no such detection yet.

## Limits

- Timing is measured on samples taken every 100 ms; shorter delays cannot be told apart.
- Results are written to the report, not stored in the database.
- The suite is checked against a deliberately broken tank (wrong relief pressure, slow alarms, a
  stuck valve that moves) to make sure it notices.

## Browser tests

Four Playwright tests drive the dashboard against the running station, covering the whole chain:
command, simulator, telemetry, command status and alarms. They use the installed Google Chrome.

```bash
docker compose up --build --detach --wait
cd web/e2e
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm ci
npm test
```

They share the single tank, so they run one at a time and reset it before and after each test.
One run sends about 15 commands; when repeating runs, raise the rate limit with
`COMMANDS_PER_MINUTE=1000 docker compose up`.
