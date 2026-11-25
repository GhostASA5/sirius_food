# Практическая работа 9

## Запуск

В каталоге `sirius_food` выполните `docker compose up --build -d`. В `.env` задайте `GRAFANA_ADMIN_PASSWORD`. Пароль для текущего рабочего окружения уже создан в этом файле. Логин Grafana — `admin`.

- API и метрики доступны на `http://localhost:8000/metrics`.
- Prometheus и список целей доступны на `http://localhost:9090/targets`.
- Дашборд Grafana открывается на `http://localhost:3001/d/sirius`.
- Jaeger открывается на `http://localhost:16686`.

## Корреляция и трассировка

Middleware принимает `X-Correlation-ID` и возвращает его в заголовках ответа. При отсутствии корректного значения создаётся UUID. Через ContextVar идентификатор доступен в слоях сервиса и репозитория. Логи выводятся в stdout в JSON с временем, уровнем, именем сервиса и correlation ID.

События Outbox сохраняют заголовки корреляции и W3C traceparent в той же транзакции, что и изменение заказа. Publisher восстанавливает контекст и создаёт span публикации RabbitMQ. Потребители извлекают контекст из заголовков сообщений. Повторы сохраняют эти заголовки. Контекст также передаётся в Celery и gRPC доставки.

Для расследования выполните `docker compose exec app python -m scripts.demo_observability`. Скрипт создаёт отдельного покупателя и курьера, оформляет и оплачивает тестовый заказ, затем печатает ID заказа и correlation ID. Скопируйте correlation ID из результата. В PowerShell выполните:

```powershell
docker compose logs --no-log-prefix app outbox kitchen | Select-String 'demo-ВАШ_ID'
```

В Jaeger выберите сервис `sirius-app` и фильтр Tags `correlation_id=demo-ВАШ_ID`. Трейс оплаты содержит HTTP, OrderService.pay, Outbox.publish, RabbitMQ.publish и kitchen.consume. Создание и оплата являются двумя HTTP-запросами с разными trace ID и общим correlation ID. Jaeger показывает длительности шагов, по ним определяют самый долгий span.

## Метрики

Prometheus собирает метрики API, RabbitMQ и Redis каждые 5 секунд. RabbitMQ использует встроенный плагин prometheus и endpoint per-object для очередей. Redis экспортируется отдельным redis_exporter. Grafana автоматически получает источник Prometheus и пять панелей — RPS по маршрутам, latency p95, ошибки 5xx, число сообщений кухни и долю попаданий Redis. Для исследования выберите временной диапазон вокруг тестового заказа.

Correlation ID, пользователь и ID заказа не используются как метки Prometheus. Это предотвращает рост числа временных рядов. Маршруты в метриках нормализованы.

## Sentry

Подключение SDK подготовлено. Чтобы увидеть событие в интерфейсе Sentry, создайте проект Python/FastAPI в своей учётной записи Sentry и скопируйте его DSN в `SENTRY_DSN` файла `.env`, затем пересоздайте API командой `docker compose up -d --force-recreate app`. DNS-настройки домена для этого не нужны.

При `DEBUG=true` администратор может вызвать `GET /observability/test-error` с access-токеном и заголовком `X-Correlation-ID: sentry-demo`. Маршрут возвращает 500, а событие содержит стек ошибки, correlation ID и ID пользователя. При выключенном DEBUG диагностический маршрут возвращает 404. Тест с локальным транспортом SDK проверяет передачу тега без отправки в интернет. Демонстрация события в настоящем Sentry требует DSN.

## Проверка

`python -m pytest tests/test_observability.py` проверяет заголовок ответа, метрики, сохранение контекста в Outbox и тег Sentry.

## Выполненное расследование

25 ноября 2026 года скрипт создал и оплатил заказ 33 с correlation ID `demo-8b8f6c1df85c`. В логах API найдены `order_created` и `order_paid`, в Outbox — `event_published`, в кухне — `order_received`. У оплаты, публикации и кухни один trace ID `14af385b4fe43443e8abdeb3d9bc549c`.

Jaeger сохранил шаги `OrderService.pay` (7,4 мс), HTTP оплаты (11 мс), `Outbox.publish` (6,2 мс), `RabbitMQ.publish` (5,4 мс), `kitchen.consume` (33 мс), `delivery.consume` (41 мс), `loyalty_earn.consume` (28 мс). Самым долгим оказался обработчик доставки. Пауза между завершением HTTP и публикацией обусловлена периодическим опросом Outbox.

Все три цели Prometheus подтверждены UP. Запросы пяти панелей Grafana вернули временные ряды. Администратор вызвал диагностическую ошибку с correlation ID `sentry-demo`, API вернул 500 и тот же заголовок. 39 тестов прошли при первоначальном прогоне, ещё один интеграционный тест RabbitMQ выполнен отдельно после запуска брокера и тоже прошёл. Отправка ошибки в реальный проект Sentry не проверена, так как DSN отсутствует.
