# The whole station in one container, for a single free web service. Build from the repository root.
# Development and CI use compose.yaml, with one container per part.
FROM node:22-bookworm-slim AS web
WORKDIR /build/dashboard
COPY web/dashboard/package.json web/dashboard/package-lock.json ./
RUN npm ci
COPY web/dashboard ./
RUN npm run build
WORKDIR /build/api
COPY web/api/package.json web/api/package-lock.json ./
RUN npm ci
COPY web/api/tsconfig.json ./
COPY web/api/src ./src
RUN npm run build && npm prune --omit=dev

FROM python:3.12-slim-bookworm
WORKDIR /app
COPY station/pyproject.toml ./station/
COPY station/src ./station/src
RUN pip install --no-cache-dir ./station && useradd --system station
COPY --from=web /usr/local/bin/node /usr/local/bin/node
COPY --from=web /build/api/package.json ./web/
COPY --from=web /build/api/node_modules ./web/node_modules
COPY --from=web /build/api/dist ./web/dist
COPY --from=web /build/dashboard/dist ./web/public
COPY deploy/start.sh ./
USER station
ENV NODE_ENV=production PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=10000 STATIC_DIR=/app/web/public
EXPOSE 10000
CMD ["bash", "start.sh"]
