# EWC Compute — Backend Dockerfile
# Multi-stage build: keeps the production image lean by separating
# dependency installation from the final runtime image.
#
# Stages:
#   builder  — installs Python deps into a venv
#   production — copies the venv and app code; runs uvicorn
#   development — extends production with dev/test deps and hot-reload
#
# Usage:
#   Production:   docker build --target production -t ewc-backend .
#   Development:  docker build --target development -t ewc-backend-dev .
#   CI:           docker build --target production -t ewc-backend:ci .

# ── Base ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN python -m venv $VIRTUAL_ENV

# ── Builder ───────────────────────────────────────────────────────────────
FROM base AS builder

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Production ────────────────────────────────────────────────────────────
FROM base AS production

# Non-root user for security
RUN addgroup --system --gid 1001 ewcgroup && \
    adduser  --system --uid 1001 --gid 1001 ewcuser

# Copy venv from builder (avoids carrying build tools into production image)
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=ewcuser:ewcgroup . .

USER ewcuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')"

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-config", "/dev/null"]

# ── Development ───────────────────────────────────────────────────────────
FROM production AS development

USER root

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

USER ewcuser

# Hot-reload enabled; single worker for deterministic test state
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload", \
     "--reload-dir", "/app/app"]
