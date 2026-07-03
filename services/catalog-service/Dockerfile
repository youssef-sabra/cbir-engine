# syntax=docker/dockerfile:1
#
# Build context is the REPOSITORY ROOT (not this directory), because the
# image needs the shared/ packages:
#   docker build -f services/catalog-service/Dockerfile .

# ---- Build stage -----------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY shared/domain-kernel ./shared/domain-kernel
COPY shared/common-libs ./shared/common-libs
COPY services/catalog-service/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt \
    ./shared/domain-kernel ./shared/common-libs

# ---- Runtime stage ----------------------------------------------------------
FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY services/catalog-service/catalog_service ./catalog_service
COPY services/catalog-service/alembic.ini ./alembic.ini
COPY services/catalog-service/docker-entrypoint.sh ./docker-entrypoint.sh

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN chown -R appuser:appuser /app && chmod +x docker-entrypoint.sh
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["./docker-entrypoint.sh"]
