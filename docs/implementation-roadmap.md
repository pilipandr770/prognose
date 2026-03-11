# Implementation Roadmap

## Product Scope

Платформа создается как prediction game и virtual portfolio platform.

Базовые правила:
- Игровые монеты выпускаются платформой и не конвертируются в реальные деньги.
- Денежный слой продукта только один: подписки через Stripe.
- В первой версии есть два независимых направления: прогнозы событий и виртуальный портфель активов.
- В первой версии есть два независимых лидерборда: predictions leaderboard и portfolios leaderboard.
- Портфель пользователя приватен по составу; публичны только агрегированные метрики и место в рейтинге.
- Денежные награды, creator monetization, копирование портфелей и платный доступ к чужим сделкам не входят в V1.

## Tech Stack

- Backend: Python + Flask
- Database: PostgreSQL
- ORM: SQLAlchemy
- Migrations: Alembic
- Auth: JWT + email verification
- Billing: Stripe
- Cache and background jobs: Redis + Celery or RQ
- Observability: structured logs + Sentry

## Architecture Approach

На первом этапе проект реализуется как модульный Flask-монолит. Это быстрее для старта и безопаснее в эксплуатации, чем ранний переход к микросервисам.

Рекомендуемая структура:

```text
backend/
  app/
    __init__.py
    config.py
    extensions.py
    api/
    models/
    services/
    tasks/
    policies/
    utils/
  migrations/
  tests/
frontend/
docs/
```

## Delivery Phases

### Phase 0. Product Freeze

Цель: зафиксировать правила продукта до начала разработки.

Результат:
- Утвержденный scope V1.
- Зафиксированная терминология продукта.
- Утвержденные публичные и приватные данные профиля.
- Утвержденные правила двух рейтингов.
- Утвержденный список запрещенных функций для первой версии.

### Phase 1. Core Platform Foundation

Цель: собрать базовый backend-каркас и инфраструктурные модули.

Включает:
- Flask app factory
- environment configs
- PostgreSQL connection
- SQLAlchemy models base
- Alembic migrations setup
- JWT auth bootstrap
- Redis integration
- background jobs setup
- error handling and audit logging

### Phase 2. Accounts, Auth and Wallet

Цель: запустить пользовательскую идентичность и внутреннюю игровую экономику.

Включает:
- регистрация и логин
- email verification
- password reset
- user profile
- public handle and avatar
- privacy flags
- verification status
- wallet ledger
- стартовое начисление 10 000 игровых евро
- idempotency keys for balance operations

### Phase 3. Prediction Events Engine

Цель: реализовать прогнозы по событиям как первый основной режим.

Включает:
- categories
- event entity
- outcomes
- deadlines
- source of truth
- draft and moderation flow
- open and locked states
- prediction positions
- public prediction history
- event settlement
- dispute support

### Phase 4. Virtual Portfolio Engine

Цель: реализовать второй основной режим с приватным составом портфеля.

Включает:
- asset catalog
- asset types
- provider symbols
- price snapshots
- buy and sell flows
- portfolio positions
- trade history
- cash balance
- performance snapshots
- public aggregated metrics
- hidden holdings in public API

### Phase 5. Ratings and Leaderboards

Цель: построить два независимых рейтинга.

Включает:
- prediction scoring
- portfolio scoring
- daily leaderboard snapshots
- seasonal leaderboard snapshots
- rank history
- percentile and badges
- suspicious user exclusion rules
- Redis caching for live reads

### Phase 6. Social Foundation

Цель: добавить базовый social layer без лишней сложности.

Включает:
- follow and unfollow
- public profiles
- activity feed
- feed for public predictions
- feed for portfolio rank changes
- user discovery basics

Не входит:
- direct messages
- comments at scale
- creator subscriptions

### Phase 7. Stripe Billing and Entitlements

Цель: реализовать единственный денежный слой платформы.

Включает:
- Free, Pro, Elite plans
- Stripe checkout
- webhooks
- subscription state sync
- entitlements layer
- feature gating on backend
- billing incidents handling

Принцип:
- Подписка открывает функции, аналитику и лимиты.
- Подписка не влияет на честность ранжирования.

### Phase 8. Anti-Abuse and Soft Verification

Цель: защитить лидерборды и продукт без жесткого friction на входе.

Включает:
- email verification
- CAPTCHA
- rate limits
- suspicious activity flags
- IP and device heuristics
- moderation tools for abuse review
- trusted status for leaderboard eligibility

Не входит в V1:
- обязательная платная identity verification

### Phase 9. Admin and Operations

Цель: сделать продукт операционно управляемым.

Включает:
- event moderation
- manual resolution tools
- disputes management
- suspicious users review
- asset catalog management
- price feed health checks
- subscription incident tools
- audit log viewer

### Phase 10. Closed Beta

Цель: проверить продукт на ограниченной аудитории до публичного запуска.

Включает:
- limited onboarding
- internal moderation runbook
- leaderboard fairness review
- abuse review
- subscription conversion review
- monitoring and incident response

## Sprint Plan

### Sprint 1

Цель: каркас backend и инфраструктура.

Scope:
- Flask app factory
- config system
- extensions module
- PostgreSQL connection
- Alembic setup
- health endpoint
- base test setup
- Docker or local dev bootstrap

Deliverable:
- backend skeleton ready for domain modules

### Sprint 2

Цель: auth, profiles and wallet ledger.

Scope:
- user model
- auth endpoints
- email verification
- profile endpoints
- wallet and wallet entries
- initial balance grant flow
- audit logging for wallet operations

Deliverable:
- users can register, verify account and receive in-game balance

### Sprint 3

Цель: prediction events core.

Scope:
- event model
- outcomes model
- moderation statuses
- create and list events
- open prediction positions
- close event for new positions by deadline
- public prediction history

Deliverable:
- users can participate in prediction events with virtual balance

### Sprint 4

Цель: settlement engine and moderation.

Scope:
- event resolution flow
- ledger updates on settlement
- idempotent settlement job
- disputes model
- moderation review flow
- admin event actions

Deliverable:
- events can be resolved safely and balances update correctly

### Sprint 5

Цель: virtual portfolio MVP.

Scope:
- asset catalog
- price snapshots
- portfolio positions
- trade endpoints
- portfolio valuation
- private holdings API
- public portfolio metrics API

Deliverable:
- users can build and track a virtual portfolio on in-game balance

### Sprint 6

Цель: leaderboards and scoring.

Scope:
- prediction scoring service
- portfolio scoring service
- daily snapshots
- leaderboard endpoints
- rank history
- minimum eligibility thresholds

Deliverable:
- two independent leaderboards are live

### Sprint 7

Цель: social foundation and subscriptions.

Scope:
- follow system
- activity feed
- public profile pages
- Stripe checkout
- webhook handling
- entitlements layer
- plan-based feature gating

Deliverable:
- social basics and paid plans are operational

### Sprint 8

Цель: anti-abuse, admin tools and beta readiness.

Scope:
- CAPTCHA
- rate limits
- suspicious user flags
- admin review screens
- price feed monitoring
- billing incident handling
- end-to-end smoke tests

Deliverable:
- platform is ready for closed beta

## Data Model Priorities

Таблицы первой волны:
- users
- user_profiles
- subscriptions
- subscription_plans
- wallets
- wallet_entries
- events
- event_outcomes
- prediction_positions
- assets
- asset_price_snapshots
- portfolio_positions
- portfolio_trades
- portfolio_snapshots
- leaderboard_snapshots
- follows
- moderation_cases
- audit_logs

## Critical Non-Functional Requirements

- Все денежные вычисления только через Decimal и numeric в PostgreSQL.
- Settlement событий должен быть идемпотентным.
- Любая операция баланса проходит через ledger.
- Публичный API никогда не раскрывает состав чужого портфеля.
- Подписки не меняют формулу рейтинга.
- Подозрительные аккаунты могут быть исключены из официальных лидербордов без удаления аккаунта.

## What Starts After This Plan

После утверждения roadmap следующий практический шаг:
1. Инициализировать backend-скелет Flask-проекта.
2. Спроектировать схему PostgreSQL и Alembic migrations для core-таблиц.
3. Реализовать auth, users и wallet ledger как первую вертикаль.

## Deferred Until Later

- AI vs Human as a dedicated product layer
- paid creator monetization
- paid portfolio sharing
- copy portfolio mechanics
- mandatory paid verification
- advanced market types beyond binary and multiple choice