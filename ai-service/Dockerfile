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
# Install torch AND torchvision from the SAME CPU wheel index so their compiled
# ops match. torchvision is a transitive dependency of open-clip-torch (and is
# touched by transformers' AutoProcessor for SigLIP 2's fast image processor);
# if it is instead pulled from PyPI it can mismatch the CPU torch build and
# fail with "operator torchvision::nms does not exist", which surfaces as
# "Could not import module 'AutoProcessor'". Installing the matched pair first
# means the later requirements-ml.txt install keeps this torchvision.
RUN if [ "$INSTALL_ML" = "true" ]; then \
        pip install --no-cache-dir --user torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
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

# Pre-create the Hugging Face cache dir owned by appuser. When the SigLIP 2
# overlay mounts a fresh named volume here (HF_HOME), Docker initializes the
# volume with THIS directory's ownership (uid 1000), so the non-root user can
# write the downloaded model weights. Without this the volume is root-owned and
# the download fails with PermissionError.
RUN mkdir -p /home/appuser/.cache/huggingface \
    && chown -R appuser:appuser /app /home/appuser/.cache
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "ai_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
