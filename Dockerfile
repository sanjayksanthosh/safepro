# ---- Stage 1: build the React frontend ----
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ---- Stage 2: Python runtime with Playwright Chromium ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DJANGO_DEBUG=0 \
    DJANGO_ALLOWED_HOSTS=* \
    PORT=8000

WORKDIR /app

# System deps needed by Playwright's Chromium (installed via --with-deps).
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

# Download Chromium + its OS libraries, and the VADER lexicon NLTK needs.
RUN python -m playwright install --with-deps chromium \
    && python -c "import nltk; nltk.download('vader_lexicon')"

# App code + pre-built frontend.
COPY . .
COPY --from=frontend-build /frontend/dist /app/frontend/dist

# File-logging handler writes to /app/logs/safepro.log; create the dir.
RUN mkdir -p /app/logs

# Collect the built SPA assets into STATIC_ROOT for WhiteNoise.
RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["sh", "start.sh"]
