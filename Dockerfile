# Gamebook Studio — API + built UI on :8888.
#   docker build -t gamebook .
#   docker run -p 8888:8888 -v gamebook-data:/data --env-file .env gamebook

# ---- Frontend build ----
FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Runtime ----
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# WeasyPrint (print/PDF export) needs pango + fonts.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 fontconfig fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
RUN uv sync --frozen --no-dev

# The player export reads frontend/dist-player; the API serves frontend/dist.
COPY --from=frontend /app/frontend/dist /app/frontend/dist
COPY --from=frontend /app/frontend/dist-player /app/frontend/dist-player

# The demo book, loaded into a fresh /data volume on first start.
COPY examples /app/examples
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

ENV PATH="/app/backend/.venv/bin:$PATH" \
    GAMEBOOK_FRONTEND_DIST=/app/frontend/dist \
    GAMEBOOK_DATA_DIR=/data \
    GAMEBOOK_LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

VOLUME /data
EXPOSE 8888
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8888/api/health')"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["gamebook", "serve", "--host", "0.0.0.0", "--port", "8888"]
