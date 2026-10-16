# Сириус.Еда

Учебный FastAPI-проект, восстановленный из приложения А лабораторной работы № 2.

## Лабораторная работа № 2

Модули `orders` и `users` разделены на транспортный слой (`router.py`), бизнес-логику (`service.py`) и доступ к данным (`repository.py`). Сервис получает репозиторий через конструктор и не импортирует FastAPI или SQLAlchemy. Создание заказа и списание баланса выполняются в одной транзакции. Внешние маршруты, структуры ответов и коды ошибок MVP сохранены.

```mermaid
flowchart LR
    Client[Клиент] --> Router[router.py]
    Router --> Service[service.py]
    Service --> Repository[repository.py]
    Repository --> DB[(PostgreSQL)]
```

## Запуск

Из каталога `sirius_food`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d db redis
uvicorn app.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs. Тесты: `pytest -q`.
