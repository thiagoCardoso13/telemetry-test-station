import type { Command } from "./types";

const ERRORS: Record<number, string> = {
  1: "unreadable payload",
  2: "unsupported",
  3: "value out of range",
  4: "valve is stuck",
};

const VALVES = ["fill", "vent", "relief"];

export const label = (name: string) => name.replaceAll("_", " ");

export function describeCommand({ name, args }: Pick<Command, "name" | "args">): string {
  if (name === "set_valve") return `${args.open ? "open" : "close"} ${args.valve} valve`;
  if (name === "inject_fault") {
    if (args.fault === "stuck_valve") return `stick ${VALVES[Number(args.magnitude) - 1]} valve`;
    return `inject ${label(String(args.fault))} (${args.magnitude})`;
  }
  return label(name);
}

export function describeStatus({ status, error }: Pick<Command, "status" | "error">): string {
  return error === null ? status : `${status}: ${ERRORS[error] ?? `error ${error}`}`;
}
