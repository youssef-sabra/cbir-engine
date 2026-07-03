# syntax=docker/dockerfile:1
#
# Build context is the REPOSITORY ROOT (needs the shared/ packages):
#   docker build -f services/query-service/Dockerfile .

FROM python:3.12-slim AS builder
WORKDIR /build
COPY shared/domain-kernel ./shared/domain-kernel
COPY shared/common-libs ./shared/common-libs
COPY services/query-service/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt \
    ./shared/domain-kernel ./shared/common-libs

FROM python:3.12-slim AS runtime
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --from=builder /root/.local /home/appuser/.local
COPY services/query-service/query_service ./query_service
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["uvicorn", "query_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
