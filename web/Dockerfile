# The web API and the dashboard it serves.
FROM node:22-alpine AS dashboard
WORKDIR /app
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard ./
RUN npm run build

FROM node:22-alpine AS api
WORKDIR /app
COPY api/package.json api/package-lock.json ./
RUN npm ci
COPY api/tsconfig.json ./
COPY api/src ./src
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production HOST=0.0.0.0 STATIC_DIR=/app/public
COPY api/package.json api/package-lock.json ./
RUN npm ci --omit=dev
COPY --from=api /app/dist ./dist
COPY --from=dashboard /app/dist ./public
USER node
EXPOSE 3000
CMD ["node", "dist/server.js"]
