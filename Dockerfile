# Bundles ffmpeg + faster-whisper + the alignment SDKs, so the only local
# requirement to run Auto-sync-LRC is Docker itself. See README.md "Quick
# start (Docker)" for the one-line run command.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Songs/lyrics are mounted here at run time (see README) - keeping it as a
# plain directory means a bind mount just works with no extra setup.
WORKDIR /data

ENTRYPOINT ["auto-sync-lrc"]
