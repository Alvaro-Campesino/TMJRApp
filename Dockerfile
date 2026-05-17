# syntax=docker/dockerfile:1.6

FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt


FROM python:3.12-slim AS runtime

ARG VERSION=dev
LABEL org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.source="https://github.com/" \
      org.opencontainers.image.title="TMJRApp"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/install/bin:${PATH}" \
    PYTHONPATH="/install/lib/python3.12/site-packages:${PYTHONPATH}" \
    TMJR_VERSION=$VERSION

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app

WORKDIR /app
COPY --from=builder /install /install
COPY tmjr ./tmjr
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY VERSION ./VERSION
COPY scripts ./scripts
RUN chmod +x scripts/*.sh && chown -R app:app /app

USER app
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:80/health || exit 1

CMD ["sh", "/app/scripts/start.sh"]
