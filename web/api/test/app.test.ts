import { afterEach, expect, test, vi } from "vitest";
import { buildApp, type Dependencies } from "../src/app.js";
import type { Reader } from "../src/db.js";
import type { Ingest } from "../src/ingest.js";
import { Hub, MAX_CLIENTS } from "../src/live.js";

const emptyReader: Reader = {
  telemetry: async () => [],
  alarms: async () => [],
  commands: async () => [],
  counters: async () => ({}),
};

function fakeIngest() {
  const sent: unknown[] = [];
  const ingest: Ingest = {
    definitions: async () => ({ status: 200, body: { parameters: [] } }),
    send: async (command) => {
      sent.push(command);
      return { status: 202, body: { id: sent.length } };
    },
  };
  return { ingest, sent };
}

let app: Awaited<ReturnType<typeof buildApp>>;
afterEach(() => app.close());

async function start(overrides: Partial<Dependencies> = {}) {
  const fake = fakeIngest();
  app = await buildApp({ reader: emptyReader, ingest: fake.ingest, ...overrides });
  return fake;
}

const post = (payload: object) => app.inject({ method: "POST", url: "/api/commands", payload });

test("health endpoint answers ok", async () => {
  await start();

  const response = await app.inject("/health");

  expect(response.json()).toEqual({ status: "ok" });
});

test("a command is passed to ingest and its answer returned", async () => {
  const { sent } = await start();
  const command = { name: "set_valve", args: { valve: "fill", open: 1 } };

  const response = await post(command);

  expect(response.statusCode).toBe(202);
  expect(response.json()).toEqual({ id: 1 });
  expect(sent).toEqual([command]);
});

test("malformed commands never reach ingest", async () => {
  const { sent } = await start();

  for (const bad of [
    {},
    { name: 5 },
    { name: "reset", extra: true },
    { name: "set_valve", args: { valve: ["fill"] } },
    { name: "x".repeat(41) },
  ]) {
    expect((await post(bad)).statusCode, JSON.stringify(bad)).toBe(400);
  }
  expect(sent).toEqual([]);
});

test("commands are rate limited", async () => {
  const { sent } = await start({ commandsPerMinute: 2 });

  const statuses = [];
  for (let i = 0; i < 3; i++) statuses.push((await post({ name: "ping" })).statusCode);

  expect(statuses).toEqual([202, 202, 429]);
  expect(sent).toHaveLength(2);
});

test("all viewers together are limited too, whatever address they claim", async () => {
  const { sent } = await start({ totalCommandsPerMinute: 2, proxyHops: 1 });

  const statuses = [];
  for (let i = 0; i < 3; i++) {
    const response = await app.inject({
      method: "POST",
      url: "/api/commands",
      headers: { "x-forwarded-for": `10.0.0.${i}` },
      payload: { name: "ping" },
    });
    statuses.push(response.statusCode);
  }

  expect(statuses).toEqual([202, 202, 429]);
  expect(sent).toHaveLength(2);
});

test("telemetry window is validated and defaults to two minutes", async () => {
  const telemetry = vi.fn(async () => []);
  await start({ reader: { ...emptyReader, telemetry } });

  await app.inject("/api/telemetry");
  await app.inject("/api/telemetry?seconds=30");

  expect(telemetry.mock.calls).toEqual([[120], [30]]);
  for (const seconds of ["0", "1000", "-5", "abc"]) {
    expect((await app.inject(`/api/telemetry?seconds=${seconds}`)).statusCode).toBe(400);
  }
});

test("a database failure is a 503 that reveals nothing", async () => {
  vi.spyOn(console, "warn").mockImplementation(() => {});
  const alarms = async () => {
    throw new Error("connect ECONNREFUSED 10.0.0.5:5432");
  };
  await start({ reader: { ...emptyReader, alarms } });

  const response = await app.inject("/api/alarms");

  expect(response.statusCode).toBe(503);
  expect(response.body).not.toContain("10.0.0.5");
});

test("the hub skips slow viewers and limits how many there are", () => {
  const hub = new Hub();
  const fast = { bufferedAmount: 0, send: vi.fn() };
  const slow = { bufferedAmount: 10_000_000, send: vi.fn() };
  hub.add(fast);
  hub.add(slow);

  hub.broadcast("hello");

  expect(fast.send).toHaveBeenCalledWith("hello");
  expect(slow.send).not.toHaveBeenCalled();
  for (let i = 2; i < MAX_CLIENTS; i++) hub.add({ bufferedAmount: 0, send() {} });
  expect(hub.add({ bufferedAmount: 0, send() {} })).toBe(false);
});

test("notifications reach a websocket viewer", async () => {
  const hub = new Hub();
  await start({ hub });
  await app.ready();
  const socket = await app.injectWS("/api/live");
  const received = new Promise<string>((resolve) =>
    socket.once("message", (data) => resolve(String(data))),
  );

  hub.broadcast('{"type":"alarm"}');

  expect(await received).toBe('{"type":"alarm"}');
  socket.terminate();
});

test("with one proxy, only the address it added counts", async () => {
  await start({ commandsPerMinute: 1, totalCommandsPerMinute: 100, proxyHops: 1 });
  const from = async (forwarded: string) =>
    (
      await app.inject({
        method: "POST",
        url: "/api/commands",
        headers: { "x-forwarded-for": forwarded },
        payload: { name: "ping" },
      })
    ).statusCode;

  expect(await from("1.1.1.1, 9.9.9.9")).toBe(202);
  expect(await from("2.2.2.2, 9.9.9.9")).toBe(429); // a made-up first address changes nothing
  expect(await from("8.8.8.8")).toBe(202);
});
