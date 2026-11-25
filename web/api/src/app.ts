import rateLimit from "@fastify/rate-limit";
import fastifyStatic from "@fastify/static";
import websocket from "@fastify/websocket";
import Fastify from "fastify";
import type { Reader } from "./db.js";
import type { Ingest } from "./ingest.js";
import { Hub } from "./live.js";

export interface Dependencies {
  reader: Reader;
  ingest: Ingest;
  hub?: Hub;
  staticDir?: string;
  commandsPerMinute?: number;
  /** For everyone together: the tank is shared, and addresses can be faked behind a proxy. */
  totalCommandsPerMinute?: number;
  /** How many reverse proxies in front of the server add to X-Forwarded-For. */
  proxyHops?: number;
}

const commandSchema = {
  type: "object",
  required: ["name"],
  additionalProperties: false,
  properties: {
    name: { type: "string", maxLength: 40 },
    args: {
      type: "object",
      maxProperties: 4,
      additionalProperties: { type: ["string", "number"] },
    },
  },
};

export async function buildApp(dependencies: Dependencies) {
  const { reader, ingest, hub = new Hub(), staticDir, commandsPerMinute = 30 } = dependencies;
  const { totalCommandsPerMinute = commandsPerMinute * 4, proxyHops = 0 } = dependencies;
  let windowStart = 0;
  let inWindow = 0;
  const app = Fastify({
    bodyLimit: 4096,
    trustProxy: proxyHops ? (_address: string, hop: number) => hop < proxyHops : false,
    // reject wrong input instead of silently converting or dropping it
    ajv: { customOptions: { coerceTypes: false, removeAdditional: false, allowUnionTypes: true } },
  });

  await app.register(rateLimit, { global: false });
  await app.register(websocket, { options: { maxPayload: 1024 } });
  if (staticDir) await app.register(fastifyStatic, { root: staticDir });

  app.setErrorHandler((error: Error & { statusCode?: number }, _request, reply) => {
    if (error.statusCode && error.statusCode < 500) {
      return reply.status(error.statusCode).send({ error: error.message });
    }
    // database or ingest away: say so, without leaking addresses
    console.warn(error.message);
    return reply.status(503).send({ error: "temporarily unavailable" });
  });

  app.get("/health", async () => ({ status: "ok" }));

  app.get("/api/definitions", async (_request, reply) => {
    const { status, body } = await ingest.definitions();
    return reply.status(status).send(body);
  });

  app.get<{ Querystring: { seconds?: string } }>(
    "/api/telemetry",
    {
      schema: {
        querystring: {
          type: "object",
          // query strings are text, so the number is checked as text
          properties: { seconds: { type: "string", pattern: "^[1-9][0-9]{0,2}$" } },
        },
      },
    },
    async (request) => reader.telemetry(Number(request.query.seconds ?? 120)),
  );

  app.get("/api/alarms", async () => reader.alarms());
  app.get("/api/commands", async () => reader.commands());
  app.get("/api/link", async () => reader.counters());

  app.post(
    "/api/commands",
    {
      schema: { body: commandSchema },
      config: { rateLimit: { max: commandsPerMinute, timeWindow: "1 minute" } },
    },
    async (request, reply) => {
      if (Date.now() - windowStart >= 60_000) {
        windowStart = Date.now();
        inWindow = 0;
      }
      if (++inWindow > totalCommandsPerMinute) {
        return reply.status(429).send({ error: "the station is busy" });
      }
      const { status, body } = await ingest.send(request.body);
      return reply.status(status).send(body);
    },
  );

  app.get("/api/live", { websocket: true }, (socket) => {
    if (!hub.add(socket)) return socket.close(1013, "too many viewers");
    socket.on("close", () => hub.remove(socket));
    socket.on("error", () => hub.remove(socket));
  });

  return app;
}
