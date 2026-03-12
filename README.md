# Prognose

Prognose is a play-money prediction game and virtual portfolio platform.

The product combines two core experiences inside one app:

- event predictions with virtual currency
- private virtual portfolios built from stocks, crypto assets, ETFs, and funds

The project is intentionally designed as a game, not a real-money betting product.
Users receive platform-issued virtual balance, can compete on leaderboards, and can buy subscriptions for product features, but there is no cash gambling layer and no real-money trading.

## Product Idea

The core product thesis is:

- prediction markets are engaging when they are easy to join and socially visible
- virtual portfolios are useful when they feel live, simple, and low-friction
- the two modes should remain separate in scoring so user skill is measured fairly

That is why Prognose keeps two distinct systems:

- a prediction system with event-based positions and its own leaderboard
- a portfolio system with virtual asset trading and a separate portfolio leaderboard

Public profiles expose high-level performance, while private portfolio holdings stay private.

## Current Stage

The project is beyond planning and early scaffolding. It is currently in a working pre-beta prototype stage.

What is already implemented:

- modular Flask backend with PostgreSQL-ready models and Alembic migrations
- JWT authentication, signup, login, wallet creation, and signup balance
- event creation, moderation, LMSR-style prediction pricing, quoting, position placement, and event resolution
- private portfolio engine with buy and sell flows, trade history, PnL, and public summary metrics
- Yahoo Finance-backed asset discovery for stocks, crypto, ETFs, and funds
- live-ish portfolio watchlist flow with database-persisted watchlists and quote refreshes
- leaderboards for predictions and portfolios
- social basics: public profiles, follow and unfollow, and feed activity
- subscription and billing layer with mock-friendly Stripe integration
- admin area for moderation, manual asset overrides, AI event generation, and user balance top-ups
- AI-assisted event generation flow with moderation-first publishing
- multi-page frontend served directly by Flask
- integration test coverage for the main product flows

What this means in practice:

- the app is already usable locally end-to-end
- the core product loops are implemented
- the main remaining work is polish, staging readiness, operational hardening, and product refinement

## Core Features

### Prediction Mode

- users create binary events or interact with approved events
- non-admin user events go to moderation first
- markets use LMSR-style pricing and return quote previews before a trade
- winning positions are settled after event resolution

### Portfolio Mode

- users search live market symbols through Yahoo Finance-backed lookup
- users can add assets to a watchlist stored in the database
- users can buy and sell virtual positions using their game balance
- holdings remain private, while aggregate performance can be shown publicly

### Admin and Operations

- approve or reject user-submitted events
- resolve events manually
- generate candidate events with OpenAI-based workflows
- manually override local assets when needed
- manually credit a user's wallet balance from the admin dashboard

## Tech Stack

- Backend: Python, Flask
- Database: PostgreSQL
- ORM: SQLAlchemy
- Migrations: Alembic
- Auth: Flask-JWT-Extended
- Billing: Stripe integration layer with mock-safe local flow
- Cache / jobs: Redis and Celery foundation
- Frontend: server-rendered static HTML, CSS, and vanilla JavaScript
- Market data: Yahoo Finance HTTP endpoints plus a websocket-backed quote cache
- AI generation: OpenAI API

## Repository Structure

```text
backend/
  app/
    api/
    models/
    services/
    tasks/
    utils/
  migrations/
  tests/
frontend/
docs/
docker-compose.yml
```

## Local Development

### 1. Start local services

Use Docker for PostgreSQL and Redis:

```powershell
docker compose up -d postgres redis
```

### 2. Configure environment

Copy the example file and set your values:

```powershell
Copy-Item backend/.env.example backend/.env
```

Important variables:

- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET_KEY`
- `SECRET_KEY`
- `OPENAI_API_KEY` if you want AI event generation enabled

### 3. Install Python dependencies

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

### 4. Apply migrations

```powershell
cd backend
python -m flask --app run.py db upgrade
```

### 5. Run the app

```powershell
cd backend
python run.py
```

Then open:

```text
http://localhost:5000/
```

## Testing

Run the backend integration suite with:

```powershell
cd backend
pytest -q
```

## Project Status Summary

Current maturity:

- product definition: solid
- backend foundation: implemented
- prediction engine: implemented
- portfolio engine: implemented
- moderation and admin tools: implemented
- AI generation flow: implemented
- local development workflow: implemented
- staging / production hardening: still pending
- long-term UX polish and analytics depth: still pending

In short, this repository is already a functioning prototype with real product structure, not just a proof of concept.

## Next Logical Milestones

- improve portfolio UX with balance-aware order sizing and cleaner trade tickets
- add admin-side audit history for wallet credits and operational actions
- improve deployment readiness for staging and production
- add CI workflows and repository automation
- expand analytics, historical views, and user-facing explanations

## Notes

- The app uses virtual balance only.
- User-created prediction events require moderation before going public.
- AI-generated events also enter moderation before becoming visible.
- Portfolio watchlists are now stored in the database per user.
