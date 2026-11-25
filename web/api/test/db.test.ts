import { readFileSync } from "node:fs";
import pg from "pg";
import { afterAll, beforeAll, describe, expect, test } from "vitest";
import { reader } from "../src/db.js";
import { Hub, listen } from "../src/live.js";

// Needs a database that may be wiped. The schema is the one the ingest service creates.
const url = process.env.TEST_DATABASE_URL;
if (!url && process.env.CI) throw new Error("CI must provide TEST_DATABASE_URL");
const schema = new URL("../../../station/src/station/ingest/schema.sql", import.meta.url);

describe.skipIf(!url)("against PostgreSQL", () => {
  const pool = new pg.Pool({ connectionString: url });

  beforeAll(async () => {
    await pool.query(
      "DROP TABLE IF EXISTS telemetry_sample, packet_log, command, alarm, link_counter",
    );
    await pool.query(readFileSync(schema, "utf-8"));
    await pool.query(`
      INSERT INTO telemetry_sample VALUES
        (now() - interval '1 hour', 'tank_pressure', 9),
        (now() - interval '2 seconds', 'tank_pressure', 2),
        (now() - interval '2 seconds', 'tank_temperature', 'NaN'),
        (now() - interval '1 second', 'tank_pressure', 3);
      INSERT INTO alarm (parameter, bound, value, raised_at, cleared_at) VALUES
        ('tank_pressure', 'high', 9, now(), now()),
        ('tank_pressure', 'low', 0.1, now() - interval '1 hour', NULL);
      INSERT INTO command (sent_at, request_id, name, args) VALUES
        (now(), '\\x00000000', 'reset', '{}');
      INSERT INTO link_counter VALUES ('received', 42);
    `);
  });
  afterAll(() => pool.end());

  test("telemetry is grouped by time inside the window", async () => {
    const points = await reader(pool).telemetry(60);

    expect(points.map((p) => p.values)).toEqual([
      { tank_pressure: 2, tank_temperature: null },
      { tank_pressure: 3 },
    ]);
    expect(points[0].time).toBeLessThan(points[1].time);
  });

  test("alarms still active come first", async () => {
    const alarms = await reader(pool).alarms();

    expect(alarms.map((a) => [a.bound, a.clearedAt === null])).toEqual([
      ["low", true],
      ["high", false],
    ]);
  });

  test("commands and counters are read as plain numbers", async () => {
    const [command] = await reader(pool).commands();

    expect(command).toMatchObject({ name: "reset", status: "sent", error: null });
    expect(typeof command.id).toBe("number");
    expect(await reader(pool).counters()).toEqual({ received: 42 });
  });

  test("the listener forwards notifications, also after losing its connection", async () => {
    const messages: string[] = [];
    const hub = new Hub();
    hub.add({ bufferedAmount: 0, send: (m) => messages.push(m) });
    const stop = listen(url!, hub, 20);
    const notifyUntilReceived = async (payload: string) => {
      await expect
        .poll(async () => {
          await pool.query("SELECT pg_notify('station', $1)", [payload]);
          return messages;
        })
        .toContain(payload);
    };

    await notifyUntilReceived("first");
    await pool.query(
      "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE query = 'LISTEN station'",
    );
    await notifyUntilReceived("second");
    await stop();
  });
});
