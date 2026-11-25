import pg from "pg";
import { buildApp } from "./app.js";
import { reader } from "./db.js";
import { ingestClient } from "./ingest.js";
import { Hub, listen } from "./live.js";

const url = process.env.DATABASE_URL;
if (!url) throw new Error("set DATABASE_URL");

const pool = new pg.Pool({ connectionString: url, max: 5, connectionTimeoutMillis: 3000 });
// an idle connection dropped by the database must not end the process
pool.on("error", (error) => console.warn(`database: ${error.message}`));

const hub = new Hub();
const stopListening = listen(url, hub);
const app = await buildApp({
  reader: reader(pool),
  ingest: ingestClient(process.env.INGEST_URL ?? "http://127.0.0.1:5003"),
  hub,
  staticDir: process.env.STATIC_DIR,
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, async () => {
    await stopListening();
    await app.close();
    await pool.end();
  });
}

await app.listen({
  port: Number(process.env.PORT ?? 3000),
  host: process.env.HOST ?? "127.0.0.1",
});
