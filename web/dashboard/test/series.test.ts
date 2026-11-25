import { expect, test } from "vitest";
import { describeCommand, describeStatus } from "../src/describe";
import { column, merge } from "../src/series";

const point = (time: number, pressure: number | null = 1) => ({
  time,
  values: { tank_pressure: pressure },
});
const times = (points: { time: number }[]) => points.map((p) => p.time);

test("live points are appended", () => {
  expect(times(merge([point(1)], [point(2)]))).toEqual([1, 2]);
});

test("history that arrives after live points is merged in order without repeats", () => {
  const merged = merge([point(3), point(4)], [point(1), point(2), point(3, 9)]);

  expect(times(merged)).toEqual([1, 2, 3, 4]);
  expect(merged[2].values.tank_pressure).toBe(9);
});

test("points older than the window are dropped", () => {
  expect(times(merge([point(0), point(50)], [point(101)], 100))).toEqual([50, 101]);
});

test("chart columns are in seconds and keep gaps", () => {
  expect(column([point(1000, 2), point(2000, null)], "tank_pressure")).toEqual([
    [1, 2],
    [2, null],
  ]);
});

test("commands and their results read as sentences", () => {
  expect(describeCommand({ name: "set_valve", args: { valve: "vent", open: 0 } })).toBe(
    "close vent valve",
  );
  expect(
    describeCommand({ name: "inject_fault", args: { fault: "stuck_valve", magnitude: 3 } }),
  ).toBe("stick relief valve");
  expect(describeCommand({ name: "clear_faults", args: {} })).toBe("clear faults");
  expect(describeStatus({ status: "failed", error: 4 })).toBe("failed: valve is stuck");
  expect(describeStatus({ status: "completed", error: null })).toBe("completed");
});
