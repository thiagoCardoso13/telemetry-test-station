import { buildApp } from "./app.js";

const app = buildApp();
const port = Number(process.env.PORT ?? 3000);

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.once(signal, () => void app.close());
}

await app.listen({ port, host: "0.0.0.0" });
