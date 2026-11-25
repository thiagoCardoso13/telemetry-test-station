import { useState } from "react";
import { sendCommand } from "./api";

const FAULTS = {
  leak: { label: "Leak", hint: "rate per second, up to 1", value: "0.2" },
  noisy_sensor: { label: "Noisy sensor", hint: "noise in bar, up to 2", value: "0.3" },
  stuck_valve: { label: "Stuck valve", hint: "valve that stays as it is", value: "3" },
};

type Fault = keyof typeof FAULTS;

export function CommandPanel({ disabled }: { disabled: boolean }) {
  const [problem, setProblem] = useState<string | null>(null);
  const [fault, setFault] = useState<Fault>("leak");
  const [magnitude, setMagnitude] = useState(FAULTS.leak.value);

  const send = async (name: string, args?: Record<string, string | number>) =>
    setProblem(await sendCommand(name, args));

  const button = (text: string, name: string, args?: Record<string, string | number>) => (
    <button type="button" disabled={disabled} onClick={() => send(name, args)}>
      {text}
    </button>
  );

  return (
    <section className="card">
      <h2>Commands</h2>
      <p className="muted">The tank is shared: everyone watching sees what you do.</p>
      {(["fill", "vent"] as const).map((valve) => (
        <div className="row" key={valve}>
          <span className="name">{valve === "fill" ? "Fill valve" : "Vent valve"}</span>
          {button("Open", "set_valve", { valve, open: 1 })}
          {button("Close", "set_valve", { valve, open: 0 })}
        </div>
      ))}
      <form
        className="row"
        onSubmit={(event) => {
          event.preventDefault();
          send("inject_fault", { fault, magnitude: Number(magnitude) });
        }}
      >
        <label className="name" htmlFor="fault">
          Fault
        </label>
        <select
          id="fault"
          value={fault}
          onChange={(e) => {
            setFault(e.target.value as Fault);
            setMagnitude(FAULTS[e.target.value as Fault].value);
          }}
        >
          {Object.entries(FAULTS).map(([key, { label }]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        {fault === "stuck_valve" ? (
          <select
            aria-label={FAULTS[fault].hint}
            value={magnitude}
            onChange={(e) => setMagnitude(e.target.value)}
          >
            <option value="1">fill</option>
            <option value="2">vent</option>
            <option value="3">relief</option>
          </select>
        ) : (
          <input
            type="number"
            step="0.1"
            min="0.1"
            required
            aria-label={FAULTS[fault].hint}
            title={FAULTS[fault].hint}
            value={magnitude}
            onChange={(e) => setMagnitude(e.target.value)}
          />
        )}
        <button type="submit" disabled={disabled}>
          Inject
        </button>
      </form>
      <div className="row">
        {button("Clear faults", "clear_faults")}
        {button("Reset tank", "reset")}
        {button("Ping", "ping")}
      </div>
      <p role="alert" className="problem">
        {problem}
      </p>
    </section>
  );
}
