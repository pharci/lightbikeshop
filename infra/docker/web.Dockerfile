FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev postgresql-client redis-tools netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock* /app/
RUN pip install -U pip && pip install "poetry>=1.7" && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi

COPY src/ /app/
COPY infra/docker/entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh

EXPOSE 8000
CMD ["/entrypoint.sh"]
