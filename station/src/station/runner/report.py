"""Turn results into the traceability matrix, as text and as one self-contained HTML page."""

from datetime import datetime
from html import escape

from .engine import SequenceResult


def trace(requirements: dict[str, str], results: list[SequenceResult]) -> dict[str, str]:
    """One verdict per requirement. Any failure wins, then anything left unverified."""
    verdicts = {}
    for requirement in requirements:
        seen = {s.verdict for r in results for s in r.steps if s.requirement == requirement}
        if not seen:
            verdicts[requirement] = "not covered"
        else:
            verdicts[requirement] = next(v for v in ("failed", "not run", "passed") if v in seen)
    return verdicts


def text(requirements: dict[str, str], results: list[SequenceResult]) -> str:
    lines = []
    for result in results:
        lines.append(f"{'PASS' if result.passed else 'FAIL'}  {result.name}: {result.title}")
        lines += [
            f"      {s.verdict}: {s.description} [{s.observed}]"
            for s in result.steps
            if s.verdict != "passed"
        ]
    lines.append("")
    lines += [
        f"{requirement}  {verdict:<11}  {requirements[requirement]}"
        for requirement, verdict in trace(requirements, results).items()
    ]
    return "\n".join(lines)


_STYLE = """
body { font: 14px/1.5 system-ui, sans-serif; max-width: 960px; margin: 24px auto; padding: 0 16px; }
table { border-collapse: collapse; width: 100%; margin-bottom: 24px; }
th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; vertical-align: top; }
.passed { background: #e3f4e3; } .failed { background: #fbe1e1; }
.not-run, .not-covered { background: #fff2d6; }
@media (prefers-color-scheme: dark) {
  body { background: #1a1a19; color: #f0efec; } th, td { border-color: #444; }
  .passed { background: #163a16; } .failed { background: #4a1c1c; }
  .not-run, .not-covered { background: #453815; }
}
"""


def _verdict(verdict: str) -> str:
    return f'<td class="{verdict.replace(" ", "-")}">{verdict}</td>'


def _table(headers: list[str], rows: list[str]) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    return f"<table><tr>{head}</tr>{''.join(f'<tr>{r}</tr>' for r in rows)}</table>"


def html(
    requirements: dict[str, str],
    results: list[SequenceResult],
    *,
    bench: str,
    created: datetime,
) -> str:
    verdicts = trace(requirements, results)
    matrix = [
        f"<td>{escape(r)}</td><td>{escape(requirements[r])}</td>{_verdict(v)}<td>"
        + ", ".join(
            escape(result.name)
            for result in results
            if any(s.requirement == r for s in result.steps)
        )
        + "</td>"
        for r, v in verdicts.items()
    ]
    sections = []
    for result in results:
        rows = [
            f"<td>{number}</td><td>{escape(s.description)}</td><td>{escape(s.requirement or '')}"
            f"</td><td>{escape(s.observed)}</td>{_verdict(s.verdict)}"
            for number, s in enumerate(result.steps, 1)
        ]
        sections.append(
            f"<h2>{escape(result.name)}: {escape(result.title)}</h2>"
            + _table(["#", "Step", "Requirement", "Observed", "Verdict"], rows)
        )
    counts = ", ".join(
        f"{list(verdicts.values()).count(v)} {v}"
        for v in ("passed", "failed", "not run", "not covered")
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Test report</title><style>{_STYLE}</style></head><body>"
        "<h1>Test report</h1>"
        f"<p>Bench: {escape(bench)}. Created {created:%Y-%m-%d %H:%M} UTC. "
        f"Requirements: {counts}.</p><h2>Traceability</h2>"
        + _table(["Requirement", "Text", "Verdict", "Verified by"], matrix)
        + "".join(sections)
        + "</body></html>"
    )
