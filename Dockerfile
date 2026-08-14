FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

# Phase 1 foundation image: validate the dependency-free models/detection slice.
# The runtime command will change when Telegram orchestration is implemented.
CMD ["python", "-m", "unittest", "discover", "-s", "tests"]
