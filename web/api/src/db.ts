import pg from "pg";

export interface TelemetryPoint {
  time: number; // milliseconds since the Unix epoch
  values: Record<string, number | null>;
}

export interface Alarm {
  id: number;
  parameter: string;
  bound: "low" | "high";
  value: number;
  raisedAt: number;
  clearedAt: number | null;
}

export interface Command {
  id: number;
  name: string;
  args: Record<string, string | number>;
  status: string;
  error: number | null;
  sentAt: number;
}

/** What the API reads. The ingest service owns the tables and is the only writer. */
export interface Reader {
  telemetry(seconds: number): Promise<TelemetryPoint[]>;
  alarms(): Promise<Alarm[]>;
  commands(): Promise<Command[]>;
  counters(): Promise<Record<string, number>>;
}

const finite = (value: number): number | null => (Number.isFinite(value) ? value : null);

export function reader(pool: pg.Pool): Reader {
  return {
    async telemetry(seconds) {
      const { rows } = await pool.query<{ time: Date; parameter: string; value: number }>(
        `SELECT time, parameter, value FROM telemetry_sample
          WHERE time > now() - make_interval(secs => $1) ORDER BY time`,
        [seconds],
      );
      const points: TelemetryPoint[] = [];
      for (const row of rows) {
        const time = row.time.getTime();
        let point = points.at(-1);
        if (point?.time !== time) {
          point = { time, values: {} };
          points.push(point);
        }
        point.values[row.parameter] = finite(row.value);
      }
      return points;
    },

    async alarms() {
      const { rows } = await pool.query(
        `SELECT id, parameter, bound, value, raised_at, cleared_at FROM alarm
          ORDER BY (cleared_at IS NULL) DESC, raised_at DESC LIMIT 20`,
      );
      return rows.map((row) => ({
        id: Number(row.id),
        parameter: row.parameter,
        bound: row.bound,
        value: row.value,
        raisedAt: row.raised_at.getTime(),
        clearedAt: row.cleared_at?.getTime() ?? null,
      }));
    },

    async commands() {
      const { rows } = await pool.query(
        `SELECT id, name, args, status, error, sent_at FROM command ORDER BY id DESC LIMIT 15`,
      );
      return rows.map((row) => ({
        id: Number(row.id),
        name: row.name,
        args: row.args,
        status: row.status,
        error: row.error,
        sentAt: row.sent_at.getTime(),
      }));
    },

    async counters() {
      const { rows } = await pool.query("SELECT name, value FROM link_counter ORDER BY name");
      return Object.fromEntries(rows.map((row) => [row.name, Number(row.value)]));
    },
  };
}
