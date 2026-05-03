FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    REVIEW_WORKSPACE_ROOT=/var/tmp/prereview

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        make \
        git \
        binutils \
        valgrind \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt -r requirements-dev.txt

RUN useradd --create-home --uid 1000 bot \
    && mkdir -p "$REVIEW_WORKSPACE_ROOT" \
    && chown -R bot:bot "$REVIEW_WORKSPACE_ROOT"

COPY --chown=bot:bot src ./src

USER bot
WORKDIR /app/src

CMD ["python", "main.py"]
