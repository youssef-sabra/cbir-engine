# syntax=docker/dockerfile:1
#
# Build context is the REPOSITORY ROOT (needs the shared/ packages):
#   docker build -f ai-service/Dockerfile .

# ---- Build stage -----------------------------------------------------------
FROM python:3.12-slim AS builder

# INSTALL_ML=true additionally installs the real-encoder dependencies (torch,
# transformers, open-clip). Left false by default so the image stays small and
# the `local` provider needs nothing extra:
#   docker build -f ai-service/Dockerfile --build-arg INSTALL_ML=true .
ARG INSTALL_ML=false

WORKDIR /build

COPY shared/common-libs ./shared/common-libs
COPY ai-service/requirements.txt ai-service/requirements-ml.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt ./shared/common-libs
RUN if [ "$INSTALL_ML" = "true" ]; then \
        pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu && \
        pip install --no-cache-dir --user -r requirements-ml.txt ; \
    fi

# ---- Runtime stage ----------------------------------------------------------
FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY ai-service/ai_service ./ai_service

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "ai_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
