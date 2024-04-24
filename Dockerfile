FROM python:3.12

WORKDIR /app

COPY poetry.lock pyproject.toml /app/

RUN apt-get update && \
    apt-get install -y postgresql-client && \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install

COPY . /app

# Команда для запуска приложения
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:8000", "lightbikeshop.wsgi:application"]