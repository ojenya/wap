# Dev image for the React + Vite web UI.
# Build context is the repo root: `docker build -f apps/web/Dockerfile .`
FROM node:22-slim

WORKDIR /app
RUN corepack enable

# Install workspace deps first (better layer caching). Copy only manifests.
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages/shared/package.json packages/shared/
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile

# App sources (mounted over in compose for hot reload).
COPY packages/shared/ packages/shared/
COPY apps/web/ apps/web/

EXPOSE 5173
# --host binds 0.0.0.0 so the port is reachable outside the container.
CMD ["pnpm", "--filter", "@wap/web", "dev", "--host"]
