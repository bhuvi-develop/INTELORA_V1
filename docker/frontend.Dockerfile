# =============================================================================
# INTELORA Frontend — build once, run anywhere
#
# Vite inlines VITE_* variables at build time, which would force a separate
# image per environment. Instead the build produces an environment-agnostic
# bundle and the entrypoint writes /config.js at container start, so a single
# image can be promoted from development to production unchanged.
# =============================================================================

# ---- Stage 1: build ---------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ---- Stage 2: serve ---------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY --from=build /build/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/frontend-entrypoint.sh /docker-entrypoint.d/40-intelora-config.sh

RUN chmod +x /docker-entrypoint.d/40-intelora-config.sh

EXPOSE 80
