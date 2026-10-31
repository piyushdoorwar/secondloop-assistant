# One image for every SecondLoop process; compose picks
# the command. Pin the base image by digest for a release.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SECONDLOOP_ROOT=/app

RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
COPY db ./db
RUN pip install --no-cache-dir .

USER app
EXPOSE 8000 8001
