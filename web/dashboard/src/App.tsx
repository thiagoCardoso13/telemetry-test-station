import { Chart } from "./Chart";
import { CommandPanel } from "./CommandPanel";
import { describeCommand, describeStatus, label } from "./describe";
import { useStation } from "./useStation";

const LINK = {
  connecting: "○ Connecting…",
  live: "● Live",
  stale: "▲ No telemetry",
};

const RANGES: Record<string, [number, number]> = {
  tank_pressure: [0, 9],
  tank_temperature: [10, 30],
};

const time = (ms: number) => new Date(ms).toLocaleTimeString("en-GB");

export function App() {
  const { definitions, points, alarms, commands, counters, link } = useStation();
  const latest = link === "live" ? points.at(-1)?.values : undefined;
  const active = alarms.filter((a) => a.clearedAt === null);
  const charted = definitions?.parameters.filter((p) => p.name in RANGES) ?? [];
  const valves = definitions?.parameters.filter((p) => p.name.endsWith("_valve")) ?? [];

  return (
    <main>
      <header>
        <h1>Telemetry &amp; Test Station</h1>
        <span className={`badge ${link}`} role="status">
          {LINK[link]}
        </span>
      </header>
      <p className="muted">A simulated pressurised tank. All data is synthetic.</p>

      {active.length > 0 && (
        <div className="banner" role="alert">
          {active.map((a) => (
            <div key={a.id}>
              ▲ Alarm: {label(a.parameter)} {a.bound === "high" ? "above" : "below"} the limit since{" "}
              {time(a.raisedAt)}
            </div>
          ))}
        </div>
      )}

      <div className="tiles">
        {charted.map((p) => (
          <div className="card tile" key={p.name}>
            <span className="muted">{label(p.name)}</span>
            <strong>
              {latest?.[p.name]?.toFixed(2) ?? "–"} <small>{p.unit}</small>
            </strong>
          </div>
        ))}
        {valves.map((p) => (
          <div className="card tile" key={p.name}>
            <span className="muted">{label(p.name)}</span>
            <strong>{latest ? (latest[p.name] ? "Open" : "Closed") : "–"}</strong>
          </div>
        ))}
      </div>

      <div className="columns">
        <div>
          {charted.map((p) => (
            <Chart
              key={p.name}
              parameter={p}
              title={p.name === "tank_pressure" ? "Pressure" : "Temperature"}
              points={points}
              atLeast={RANGES[p.name]}
            />
          ))}
        </div>
        <div>
          <CommandPanel disabled={link === "connecting"} />
          <section className="card">
            <h2>Recent commands</h2>
            <ul>
              {commands.map((c) => (
                <li key={c.id}>
                  <span className="muted">{time(c.sentAt)}</span> {describeCommand(c)} —{" "}
                  <span className={c.error === null ? "" : "problem"}>{describeStatus(c)}</span>
                </li>
              ))}
              {commands.length === 0 && <li className="muted">No commands yet.</li>}
            </ul>
          </section>
          <section className="card">
            <h2>Alarm history</h2>
            <ul>
              {alarms.map((a) => (
                <li key={a.id}>
                  {a.clearedAt === null ? "▲ active" : "✓ cleared"}: {label(a.parameter)} {a.bound}{" "}
                  <span className="muted">
                    {time(a.raisedAt)}
                    {a.clearedAt !== null && ` to ${time(a.clearedAt)}`}
                  </span>
                </li>
              ))}
              {alarms.length === 0 && <li className="muted">No alarms.</li>}
            </ul>
          </section>
          <section className="card">
            <h2>Link</h2>
            <dl>
              {Object.entries(counters).map(([name, value]) => (
                <div key={name}>
                  <dt>{label(name)}</dt>
                  <dd>{value.toLocaleString("en-GB")}</dd>
                </div>
              ))}
            </dl>
          </section>
        </div>
      </div>
    </main>
  );
}
