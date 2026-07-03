# syntax=docker/dockerfile:1
#
# Build context is the REPOSITORY ROOT (needs the shared/ packages):
#   docker build -f workers/ingestion-worker/Dockerfile .

FROM python:3.12-slim AS builder
WORKDIR /build
COPY shared/common-libs ./shared/common-libs
COPY workers/ingestion-worker/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt ./shared/common-libs

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=builder /root/.local /home/appuser/.local
COPY workers/ingestion-worker/ingestion_worker ./ingestion_worker
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN chown -R appuser:appuser /app
USER appuser

# No HTTP port — this is a queue consumer. Liveness in Kubernetes would be an
# exec probe on the process; Compose just relies on `restart: unless-stopped`.
CMD ["python", "-m", "ingestion_worker.main"]
