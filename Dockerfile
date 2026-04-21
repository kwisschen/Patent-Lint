# ---- Stage 1: Build patentlint wheel ----
FROM python:3.12-slim AS wheel-build
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
# ADR-139: hatchling force-include copies frontend/src/i18n/locales/
# into patentlint/_locales/ inside the wheel at build time so the
# Python i18n helper (src/patentlint/i18n.py) can load locale JSON
# without depending on a separate install path. The locales dir must
# therefore be present in the build context here.
COPY frontend/src/i18n/locales frontend/src/i18n/locales
RUN pip wheel . --no-deps -w /wheels/

# ---- Stage 2: Build frontend ----
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Copy pre-built wheel into public/ so Vite includes it in dist/
COPY --from=wheel-build /wheels/*.whl ./public/
# Run vite build directly (skip build:wheel since wheel is already in public/)
RUN npx vite build

# ---- Stage 3: Python runtime ----
FROM python:3.12-slim AS runtime
LABEL org.opencontainers.image.licenses="LicenseRef-PolyForm-Strict-1.0.0"

# System deps for weasyprint PDF rendering + CJK fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libffi-dev \
    shared-mime-info \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (leverage layer caching)
COPY pyproject.toml README.md ./
COPY src/ src/
# Same ADR-139 reason as wheel-build stage: hatchling needs the
# locales dir in the build context to satisfy its force-include rule.
COPY frontend/src/i18n/locales frontend/src/i18n/locales
RUN pip install --no-cache-dir ".[api]"

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist frontend/dist

EXPOSE 8000

CMD ["uvicorn", "patentlint.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
