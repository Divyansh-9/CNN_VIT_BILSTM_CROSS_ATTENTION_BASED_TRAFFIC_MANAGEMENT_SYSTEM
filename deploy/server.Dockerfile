# The server image: FastAPI server, MQTT ingest and the built dashboard (D15).
# One image, two services: `server` and `ingest` run it with different commands.
# No secret, weight, frame or dataset enters any layer: secrets arrive at run
# time, and .dockerignore keeps deploy/secrets/, data/ and models/ out of the
# build context.

# ---- the dashboard, built the way CI's dashboard job builds it (Node 22) ---------
FROM node:22.23.2-alpine AS dashboard
WORKDIR /dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY dashboard/ ./
ARG VITE_STMS_HOSTED=0
RUN VITE_STMS_HOSTED=$VITE_STMS_HOSTED npm run build

# ---- the commit behind every result file, from the real history -----------------
FROM python:3.12.10-slim-bookworm AS evidence
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /repo
COPY .git ./.git
COPY deploy/evidence_commits.py ./
RUN python evidence_commits.py --git-dir .git --out /evidence_commits.json

# ---- the runtime -------------------------------------------------------------
FROM python:3.12.10-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    STMS_EVIDENCE_COMMITS=/app/evidence_commits.json
WORKDIR /app
# The API and MQTT ingest share the base runtime. Video analysis is opt-in.
COPY requirements.txt /tmp/requirements.txt
RUN grep -iE '^(fastapi|pydantic|uvicorn|paho-mqtt)==' /tmp/requirements.txt > /tmp/server.txt \
    && test "$(wc -l < /tmp/server.txt)" -eq 4 \
    && pip install --no-cache-dir -r /tmp/server.txt \
    && mv /tmp/requirements.txt /tmp/video-pins.txt && rm /tmp/server.txt
# Hosted analysis adds the CPU detector to the existing API runtime.
ARG STMS_INSTALL_VIDEO=0
RUN if [ "$STMS_INSTALL_VIDEO" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
      && rm -rf /var/lib/apt/lists/* \
      && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
          torch==2.13.0+cpu torchvision==0.28.0+cpu \
      && grep -iE '^(ultralytics|opencv-python-headless|lap|scipy|pyyaml|numpy)==' /tmp/video-pins.txt > /tmp/video.txt \
      && pip install --no-cache-dir -r /tmp/video.txt \
      && rm /tmp/video.txt; \
    fi && rm /tmp/video-pins.txt
COPY contracts/ ./contracts/
COPY server/ ./server/
COPY edge/ ./edge/
COPY scripts/ ./scripts/
COPY mfstnet/ ./mfstnet/
COPY cameras/ ./cameras/
COPY indiatrafficnet/class_mapping.yaml ./indiatrafficnet/class_mapping.yaml
COPY experiments/results/bellevue_pilot/p103_results.json \
     experiments/results/bellevue_pilot/p105_results.json \
     experiments/results/bellevue_pilot/p105_eligibility.json \
     experiments/results/bellevue_pilot/p105_ridge_v1.json \
     experiments/results/bellevue_pilot/persistence_v1.json \
     ./experiments/results/bellevue_pilot/
COPY experiments/results/ceiling/ceiling_stats.json ./experiments/results/ceiling/ceiling_stats.json
COPY --from=dashboard /dashboard/dist ./dashboard/dist
COPY --from=evidence /evidence_commits.json ./evidence_commits.json
RUN useradd --create-home --uid 10001 stms && mkdir -p data/server && chown stms:stms data/server
USER stms
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=12 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
