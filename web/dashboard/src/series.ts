import type { Point } from "./types";

export const WINDOW_MS = 120_000;

/**
 * Join history and live points: ordered by time, one point per instant, and only the
 * last two minutes counted from the newest one.
 */
export function merge(current: Point[], incoming: Point[], windowMs = WINDOW_MS): Point[] {
  if (incoming.length === 0) return current;
  const last = current.at(-1)?.time ?? -Infinity;
  let all: Point[];
  if (incoming.length === 1 && incoming[0].time > last) {
    all = [...current, incoming[0]]; // the usual case: one new point at the end
  } else {
    const byTime = new Map(current.map((p) => [p.time, p]));
    for (const point of incoming) byTime.set(point.time, point);
    all = [...byTime.values()].sort((a, b) => a.time - b.time);
  }
  const cutoff = all[all.length - 1].time - windowMs;
  return all[0].time < cutoff ? all.filter((p) => p.time >= cutoff) : all;
}

/** Columns in the shape the chart wants: times in seconds, then values. */
export function column(points: Point[], parameter: string): [number[], (number | null)[]] {
  return [points.map((p) => p.time / 1000), points.map((p) => p.values[parameter] ?? null)];
}
