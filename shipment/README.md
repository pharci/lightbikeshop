# shipment

Сервис отгрузки для Wildberries и Ozon с интеграцией МойСклад.

Проект очищен от OpenAI Sites/ChatGPT Auth, Cloudflare Workers, Wrangler, Vinext и D1. Приложение работает как обычный Next.js 16 Node.js сервис. Локальное состояние хранится в SQLite-файле `/data/shipment.sqlite`.

## Переменные окружения

Переменные передаются из общего файла проекта:

`ops/env/.env`

Обязательные для Basic Auth:

- `shipment_BASIC_USER`
- `shipment_BASIC_PASSWORD`

Если они отсутствуют, приложение намеренно отвечает HTTP 500 вместо запуска без защиты.

API-учётки WB/Ozon/МойСклад приложение получает из переменных окружения `WB_API_KEY`, `OZON_CLIENT_ID`, `OZON_API_KEY` и `MOYSKLAD_TOKEN`. Они не кладутся в образ Docker.

## Docker Compose

Сервис добавлен в `docker-compose.service.yml`. Он рассчитан на запуск вместе с существующим `docker-compose.yml` из корня проекта:

`docker compose -f docker-compose.yml -f shipment/docker-compose.service.yml up -d --build`

`env_file` указывает на `./ops/env/.env`, то есть используется общий env-файл проекта.

Путь `/data` вынесен в Docker volume `shipment_data`, поэтому SQLite не исчезает при пересоздании контейнера.

## Nginx

Добавить `nginx-shipment.conf` в существующую конфигурацию nginx. Для сервиса используется отдельный hostname, а не `/shipment/`, чтобы не переделывать Next routing/basePath.

Nginx должен находиться в той же Docker network, что и `shipment`. При использовании общего compose это произойдёт автоматически, если существующий nginx подключён к default network compose.

После изменения конфигурации nginx проверить её и перезагрузить контейнер nginx.

## Локальный запуск

Требуется Node.js 22.16+.

`npm install`

`shipment_BASIC_USER=test shipment_BASIC_PASSWORD=test npm run dev`

## Важное замечание по прежней D1

Старое состояние Cloudflare D1/.wrangler автоматически не переносится. Новый контейнер создаёт чистый SQLite, потому что прежний проект был Cloudflare runtime-проектом.
