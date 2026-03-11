# Local Dev Stack

## Recommendation Right Now

Сейчас лучше использовать локальный PostgreSQL в контейнере и не подключать shared Render PostgreSQL как основную dev-базу.

Почему это лучше на текущем этапе:
- локальная база изолирована от других проектов;
- можно спокойно пересоздавать схему и миграции без риска задеть production-like данные;
- backend и frontend уже готовы к активной локальной разработке и быстрому циклу правок;
- Stripe webhook в любом случае пока не стоит доводить до полного real flow до публичного URL.

## Recommended Flow

1. Поднять локальные сервисы:

```powershell
docker compose up -d postgres redis
```

2. Использовать локальный `DATABASE_URL` из [backend/.env.example](backend/.env.example).

3. Render PostgreSQL оставить для следующего этапа:
- после деплоя staging/demo;
- с отдельной схемой для этого проекта;
- с прогоном Alembic migrations против выделенной схемы.

## About Render Schema

Если позже захотим использовать один Render PostgreSQL на несколько проектов, для этого проекта надо будет:
- завести отдельную схему, например `prognose_app`;
- настроить `search_path` или schema-aware metadata;
- прогнать миграции строго в эту схему.

На текущем этапе это лишняя сложность и риск для разработки.

## Stripe Right Now

Тестовые ключи можно добавить уже сейчас, но полноценный webhook flow лучше включать позже:
- после деплоя на Render/VPS;
- когда будет стабильный публичный URL;
- когда можно будет привязать Stripe webhook endpoint без туннелей и временных прокси.

Пока billing-слой уже подготовлен для mock checkout и для будущего Stripe integration layer.

## Frontend Access

Frontend теперь обслуживается самим Flask backend.

После запуска backend можно открыть в браузере:

```text
http://localhost:5000/
```

Это самый простой режим для тестов и быстрых доработок UI без отдельного frontend build step.