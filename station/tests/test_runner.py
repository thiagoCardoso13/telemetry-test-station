from datetime import UTC, datetime

import pytest

from station.ingest import alarms
from station.runner import report
from station.runner.__main__ import main
from station.runner.bench import SimulatedBench
from station.runner.conditions import Sample, parse
from station.runner.engine import SequenceResult, StepResult, run
from station.runner.model import load_requirements, load_sequence, load_sequences
from station.simulator import tank

REQUIREMENTS = load_requirements()


def verdicts(*, include_faults=False):
    results = run(SimulatedBench(), load_sequences(REQUIREMENTS, include_faults=include_faults))
    return report.trace(REQUIREMENTS, results), results


def failing(**options) -> set[str]:
    return {r for r, v in verdicts(**options)[0].items() if v in ("failed", "not run")}


def test_the_healthy_tank_passes_every_covered_requirement():
    traced, results = verdicts()

    assert all(r.passed for r in results)
    assert [r for r, v in traced.items() if v == "not covered"] == ["REQ-007", "REQ-011"]
    assert sum(v == "passed" for v in traced.values()) == 9


def test_the_fault_demonstration_fails_the_requirement_it_breaks():
    traced, results = verdicts(include_faults=True)

    assert traced["REQ-006"] == "failed"
    assert traced["REQ-007"] == "passed"
    assert [r.name for r in results if not r.passed] == ["05_stuck_relief"]


# The suite is only worth something if it notices a broken tank. Break it on purpose:


def test_a_relief_valve_set_too_high_is_noticed(monkeypatch):
    monkeypatch.setattr(tank, "RELIEF_OPENS_BAR", 9.0)

    assert {"REQ-004", "REQ-006"} <= failing()


def test_a_relief_valve_that_never_closes_is_noticed(monkeypatch):
    monkeypatch.setattr(tank, "RELIEF_CLOSES_BAR", 0.0)

    assert "REQ-005" in failing()


def test_slow_alarms_are_noticed(monkeypatch):
    original = alarms.AlarmMonitor.__init__
    monkeypatch.setattr(
        alarms.AlarmMonitor, "__init__", lambda self, samples_to_change=25: original(self, 25)
    )

    assert {"REQ-007", "REQ-008"} <= failing(include_faults=True)


def test_a_stuck_valve_that_moves_anyway_is_noticed(monkeypatch):
    def always_moves(self, name, is_open):
        self.valves[name] = is_open

    monkeypatch.setattr(tank.Tank, "set_valve", always_moves)

    assert "REQ-009" in failing()


def test_a_weak_fill_stops_the_sequence_and_marks_the_rest_not_run(monkeypatch):
    monkeypatch.setattr(tank, "FILL_RATE", 0.001)

    _, results = verdicts()

    first = results[0]
    assert [s.verdict for s in first.steps[-4:]] == ["failed", "not run", "not run", "not run"]


@pytest.mark.parametrize(
    "yaml",
    [
        "steps: []",
        "{title: t, steps: [{sleep: 1}]}",
        "{title: t, steps: [{wait: 1, check: x}]}",
        "{title: t, steps: [{check: 'tank_pressure > 1'}]}",
        "{title: t, steps: [{check: 'tank_pressure > 1', requirement: REQ-999}]}",
        "{title: t, steps: [{check: 'pressure > 1', requirement: REQ-001}]}",
        "{title: t, steps: [{check: 'tank_pressure => 1', requirement: REQ-001}]}",
        "{title: t, steps: [{command: self_destruct}]}",
        "{title: t, steps: [{command: reset, expect: maybe}]}",
        "{title: t, steps: [{wait_for: 'tank_pressure > 1', timout: 3}]}",
        "{title: t, steps: [{response: {when: 'tank_pressure > 1'}, requirement: REQ-001}]}",
    ],
)
def test_mistakes_in_a_sequence_are_refused_before_running(tmp_path, yaml):
    path = tmp_path / "bad.yaml"
    path.write_text(yaml)

    with pytest.raises(ValueError):
        load_sequence(path, REQUIREMENTS)


def test_conditions_read_values_and_alarms():
    sample = Sample(0, {"tank_pressure": 8.5}, frozenset({("tank_pressure", "high")}))

    assert parse("tank_pressure > 8").holds(sample)
    assert parse("alarm tank_pressure high").holds(sample)
    assert not parse("no alarm tank_pressure high").holds(sample)
    assert parse("no alarm tank_pressure low").holds(sample)


def result(*pairs) -> list[SequenceResult]:
    return [SequenceResult("s", "t", [StepResult("d", r, v) for r, v in pairs])]


def test_one_failure_outweighs_passes_and_unrun_steps_are_not_passes():
    requirements = dict.fromkeys(["a", "b", "c", "d"], "text")

    traced = report.trace(
        requirements,
        result(
            ("a", "passed"), ("a", "failed"), ("b", "passed"), ("b", "not run"), ("c", "passed")
        ),
    )

    assert traced == {"a": "failed", "b": "not run", "c": "passed", "d": "not covered"}


def test_the_html_report_escapes_what_it_shows():
    page = report.html(
        {"REQ-1": "<script>alert(1)</script>"},
        result(("REQ-1", "passed")),
        bench="test",
        created=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert "<script>" not in page
    assert "&lt;script&gt;" in page


def test_command_line_exit_codes_and_report_file(tmp_path, capsys):
    target = tmp_path / "out" / "report.html"

    assert main(["--report", str(target)]) == 0
    assert main(["--include-faults"]) == 1
    assert "REQ-011  not covered" in capsys.readouterr().out
    assert target.read_text().startswith("<!doctype html>")
