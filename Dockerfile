FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends g++ cmake make \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt

FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data PORT=8000
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home app \
    && mkdir /data && chown app:app /data
WORKDIR /app
COPY requirements.txt .
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels
COPY app.py matter.py scanner.py label_features.py text_recognition.py ./
COPY static ./static
USER app
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "90", "app:app"]

# Home Assistant uses a root-owned /data volume. This launcher prepares only
# /data/matterbase, drops privileges, and starts the very same Flask application.
FROM runtime AS homeassistant
USER root
ARG BUILD_ARCH
ARG ADDON_VERSION=1.0.0-ha.3
LABEL io.hass.name="Matterbase" io.hass.description="Private Matter pairing-code inventory" \
      io.hass.type="addon" io.hass.version="${ADDON_VERSION}" io.hass.arch="${BUILD_ARCH}"
COPY homeassistant/run.py /app/addon_run.py
CMD ["python", "/app/addon_run.py"]

# Keep the default docker build / Compose target standalone and non-root.
FROM runtime AS standalone
