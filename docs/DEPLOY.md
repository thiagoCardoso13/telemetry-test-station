# Deploying the public demo

One free [Render](https://render.com) web service runs the whole station
([`deploy/Dockerfile`](../deploy/Dockerfile)) with a free [Neon](https://neon.com) PostgreSQL.
Neither needs a payment card at the time of writing.

The demo is at <https://telemetry-test-station.onrender.com>.

## 1. Database (Neon)

1. Create a project in the Frankfurt region.
2. Copy the **direct** connection string: turn connection pooling **off**. The live dashboard uses
   `LISTEN`/`NOTIFY`, which a pooled (transaction mode) connection does not support.

## 2. Service (Render)

1. New → Blueprint, and choose this repository. Render reads [`render.yaml`](../render.yaml).
2. Paste the connection string when asked for `DATABASE_URL`. It is a secret: nowhere else.
3. Wait for the first build, then open the service address.

Later pushes to `main` deploy after CI passes.

## 3. Check

- The page says **Live** and shows two charts.
- Open the fill valve: pressure rises and the command ends as `completed`.
- `STATION_URL=https://<address> npm test` in `web/e2e` runs the browser tests against it. They
  command the shared tank, so do it before sharing the link.

## Variables

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | none, required | PostgreSQL connection string |
| `KEEP_MINUTES` | 10 | History kept, to stay small |
| `PROXY_HOPS` | 0 | Reverse proxies in front, to rate limit by visitor address |
| `COMMANDS_PER_MINUTE` | 30 | Per address; everyone together gets four times this |

## Free tier limits (looked up in November 2026, from third-party and vendor pages)

| | Limit | What it means here |
|---|---|---|
| Render | 512 MB, a fraction of a CPU | The image used about 80 MB under `--memory=512m --cpus=0.1` |
| Render | 750 instance hours a month, shared by all free services in the workspace | Shared with other demos |
| Render | Sleeps after 15 minutes without inbound traffic; waking takes about a minute | First visit is slow; do not keep it awake artificially |
| Neon | 100 compute hours a month per project | Used only while the service is awake |
| Neon | 5 GB of data transfer a month | A history load is under 0.5 MB |

## Checked on the real services (26 November 2026)

- The blueprint deploys, and the four browser tests pass against the public address.

## Known issue and open points

- `PROXY_HOPS=1` does not match Render's proxies: requests from one address were counted in
  several separate rate limits, so the per-address limit is not reliable. The limit for everyone
  together does not depend on the address.
- Whether a viewer who only watches keeps the service awake is not verified. The page reconnects
  by itself.
