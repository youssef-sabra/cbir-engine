# syntax=docker/dockerfile:1
#
# Builds an OCI-compliant image. Buildable identically with `docker build`
# or `podman build` — no Docker-specific features are used, consistent with
# the project's decision to use Podman for CI/production builds while
# allowing Docker for local development (docs/TECH_STACK.md Section 6).

# ---- Build stage -----------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- Runtime stage ----------------------------------------------------------
FROM python:3.12-slim AS runtime

# Run as a non-root user by default -- important both for Docker and for
# Podman's rootless-by-default model (docs/TECH_STACK.md Section 6).
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY app ./app

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
