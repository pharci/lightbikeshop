FROM python:3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    DEBIAN_FRONTEND=noninteractive \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

RUN set -eux; \
    apt-get update -o Acquire::Retries=3 \
                   -o APT::Get::AllowReleaseInfoChange::Suite=true \
                   -o APT::Get::AllowReleaseInfoChange::Version=true \
                   -o APT::Get::AllowReleaseInfoChange::Codename=true; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        netcat-openbsd \
        curl; \
    rm -rf /var/lib/apt/lists/*

COPY infra/certs/russian_trusted_root_ca_pem.crt \
     /usr/local/share/ca-certificates/russian_trusted_root_ca_pem.crt

COPY infra/certs/russian_trusted_sub_ca_pem.crt \
     /usr/local/share/ca-certificates/russian_trusted_sub_ca_pem.crt

RUN update-ca-certificates

COPY pyproject.toml poetry.lock* /app/

RUN pip install --no-cache-dir -U pip "poetry>=1.7" && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi

COPY src/ /app/
COPY infra/docker/launcher.py /launcher.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --retries=5 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',8000)); s.close()"

CMD ["python", "/launcher.py"]