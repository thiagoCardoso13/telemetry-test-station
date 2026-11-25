"""Executes sequences on a bench and records what was observed."""

from dataclasses import dataclass, field

from .bench import PERIOD_S, Bench, BenchError
from .model import Sequence, Step

# time after a reset for alarms of the previous sequence to clear
SETTLE_S = 1.0


@dataclass(frozen=True)
class StepResult:
    description: str
    requirement: str | None
    verdict: str  # "passed", "failed" or "not run"
    observed: str = ""


@dataclass
class SequenceResult:
    name: str
    title: str
    steps: list[StepResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(s.verdict == "passed" for s in self.steps)


def _wait_for(bench: Bench, step: Step) -> tuple[bool, str]:
    # only what happens from now on counts
    start = len(bench.samples())
    waited = 0.0
    while True:
        new = bench.samples()[start:]
        for sample in new:
            if step.condition.holds(sample):
                return True, f"after {sample.time - new[0].time:.1f} s"
        if waited >= step.seconds:
            seen = step.condition.observed(new[-1]) if new else "no telemetry"
            return False, f"timed out, last {seen}"
        bench.wait(PERIOD_S * 2)
        waited += PERIOD_S * 2


def _always(bench: Bench, step: Step) -> tuple[bool, str]:
    start = len(bench.samples())
    bench.wait(step.seconds)
    window = bench.samples()[start:]
    if not window:
        return False, "no telemetry"
    for sample in window:
        if not step.condition.holds(sample):
            when = sample.time - window[0].time
            return False, f"{step.condition.observed(sample)} at {when:.1f} s"
    return True, f"held in {len(window)} samples"


def _response(bench: Bench, step: Step) -> tuple[bool, str]:
    """Judge the first occurrence of the trigger since the start of the sequence."""

    def first(samples, condition, start=0):
        return next((i for i in range(start, len(samples)) if condition.holds(samples[i])), None)

    samples = bench.samples()
    start = first(samples, step.after) if step.after else 0
    trigger = None if start is None else first(samples, step.when, start)
    if trigger is None:
        return False, f"{step.when.text} never happened"

    deadline = samples[trigger].time + step.seconds
    if samples[-1].time < deadline:
        bench.wait(deadline - samples[-1].time + PERIOD_S)
        samples = bench.samples()
    answer = first(samples, step.condition, trigger)
    if answer is None:
        return False, f"never: {step.condition.observed(samples[-1])}"
    delay = samples[answer].time - samples[trigger].time
    # half a period of slack for clock rounding
    return delay <= step.seconds + PERIOD_S / 2, f"after {delay:.2f} s"


def _run_step(bench: Bench, step: Step) -> tuple[bool, str]:
    match step.kind:
        case "command":
            result = bench.send(step.command, step.args)
            observed = result.status
            if result.error is not None:
                observed += f" (error {result.error})"
            return result.status == step.expect, observed
        case "wait":
            bench.wait(step.seconds)
            return True, ""
        case "wait_for":
            return _wait_for(bench, step)
        case "check":
            bench.wait(PERIOD_S * 2)
            samples = bench.samples()
            if not samples:
                return False, "no telemetry"
            return step.condition.holds(samples[-1]), step.condition.observed(samples[-1])
        case "always":
            return _always(bench, step)
        case "response":
            return _response(bench, step)
    raise ValueError(step.kind)


def _prepare(bench: Bench) -> None:
    if bench.send("reset", {}).status != "completed":
        raise BenchError("could not reset the tank")
    bench.wait(SETTLE_S)
    bench.mark()
    bench.wait(PERIOD_S * 3)


def run_sequence(bench: Bench, sequence: Sequence) -> SequenceResult:
    """A failed check goes on to the next step; a step the rest depends on stops the sequence."""
    _prepare(bench)
    result = SequenceResult(sequence.name, sequence.title)
    stopped = False
    for step in sequence.steps:
        if stopped:
            result.steps.append(StepResult(step.description, step.requirement, "not run"))
            continue
        passed, observed = _run_step(bench, step)
        verdict = "passed" if passed else "failed"
        result.steps.append(StepResult(step.description, step.requirement, verdict, observed))
        stopped = not passed and step.kind in ("command", "wait_for")
    return result


def run(bench: Bench, sequences: list[Sequence]) -> list[SequenceResult]:
    try:
        return [run_sequence(bench, sequence) for sequence in sequences]
    finally:
        # leave a shared tank the way it was found
        bench.send("reset", {})
