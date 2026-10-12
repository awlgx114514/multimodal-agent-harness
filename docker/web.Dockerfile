FROM mcr.microsoft.com/devcontainers/javascript-node:1-22-bookworm AS build

ENV PNPM_HOME=/pnpm \
    NODE_HOME=/opt/node \
    TMPDIR=/workspace/.cache/temp
ENV PATH=$NODE_HOME/bin:$PNPM_HOME:$PATH
WORKDIR /workspace
COPY .cache/node-dist.tar.xz /workspace/node-dist.tar.xz
RUN mkdir -p "$NODE_HOME" "$TMPDIR" \
    && tar -xJf /workspace/node-dist.tar.xz -C "$NODE_HOME" --strip-components=1 \
    && rm /workspace/node-dist.tar.xz \
    && corepack enable \
    && corepack prepare pnpm@11.20.0 --activate
COPY pnpm-lock.yaml pnpm-workspace.yaml ./
COPY web/package.json ./web/package.json
RUN pnpm install --frozen-lockfile
COPY web ./web
RUN pnpm --dir web build

FROM python:3.12.10-slim-bookworm AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    TMPDIR=/app/.cache/temp
COPY --from=build /opt/node /opt/node
ENV PATH=/opt/node/bin:$PATH
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app app \
    && mkdir -p "$TMPDIR" \
    && chown -R app:app /app/.cache
WORKDIR /app
COPY --from=build --chown=app:app /workspace/web/.next/standalone ./
COPY --from=build --chown=app:app /workspace/web/.next/static ./web/.next/static
COPY --chown=app:app docker/web-entrypoint.sh /usr/local/bin/web-entrypoint
USER app
EXPOSE 3000
WORKDIR /app/web
ENTRYPOINT ["web-entrypoint"]
CMD ["node", "server.js"]
