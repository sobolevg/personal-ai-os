FROM python:3.12-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

# Phase 1 image includes FFmpeg for isolated Instagram audio preparation.
# The runtime command will change when Telegram orchestration is implemented.
CMD ["python", "-m", "unittest", "discover", "-s", "tests"]
