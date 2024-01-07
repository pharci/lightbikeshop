FROM python:3.12

# Установите рабочий каталог в контейнере
WORKDIR /app

# Копируйте файлы зависимостей в контейнер
COPY poetry.lock pyproject.toml /app/
RUN pip install poetry
RUN poetry config virtualenvs.create false
RUN poetry install

# Копируйте остальные файлы приложения в контейнер
COPY . /app

# Соберите статические файлы, если ваше приложение это требует
# RUN python manage.py collectstatic --no-input

# Запускаем Gunicorn вместо встроенного сервера Django
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:8000", "lightbikeshop.wsgi:application"]