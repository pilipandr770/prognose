from decimal import Decimal


def test_live_health_endpoint(client):
    response = client.get("/api/health/live")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["service"] == "prognose-backend"


def test_frontend_index_is_served(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Prognose" in response.data


def test_login_and_register_pages_are_served(client):
    login_response = client.get("/login")
    register_response = client.get("/register")
    dashboard_response = client.get("/dashboard")

    assert login_response.status_code == 200
    assert register_response.status_code == 200
    assert dashboard_response.status_code == 200
    assert b"Login" in login_response.data
    assert b"Register" in register_response.data
    assert b"\xd0\x9b\xd0\xb8\xd1\x87\xd0\xbd\xd1\x8b\xd0\xb9 \xd0\xba\xd0\xb0\xd0\xb1\xd0\xb8\xd0\xbd\xd0\xb5\xd1\x82" in dashboard_response.data


def test_register_login_and_fetch_profile(client):
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "handle": "forecastfox",
            "password": "strong-pass-123",
        },
    )

    assert register_response.status_code == 201
    register_payload = register_response.get_json()
    assert register_payload["user"]["wallet_balance"] == "10000.00"

    login_response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "strong-pass-123"},
    )

    assert login_response.status_code == 200
    login_payload = login_response.get_json()
    assert login_payload["access_token"]

    profile_response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {login_payload['access_token']}"},
    )

    assert profile_response.status_code == 200
    profile_payload = profile_response.get_json()
    assert profile_payload["handle"] == "forecastfox"
    assert profile_payload["wallet"]["current_balance"] == "10000.00"
    assert profile_payload["social"]["unread_notifications_count"] == 0


def test_create_event_and_place_prediction(client):
    register_response = client.post(
        "/api/auth/register",
        json={
            "email": "maker@example.com",
            "handle": "marketmaker",
            "password": "strong-pass-123",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/auth/login",
        json={"email": "maker@example.com", "password": "strong-pass-123"},
    )
    token = login_response.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_event_response = client.post(
        "/api/events",
        headers=headers,
        json={
            "title": "Will BTC close above $100k by end of 2026?",
            "description": "Market prediction test event",
            "category": "markets",
            "source_of_truth": "CoinMarketCap close price",
            "closes_at": "2026-12-01T00:00:00Z",
            "resolves_at": "2026-12-31T23:59:59Z",
            "outcomes": ["Yes", "No"],
        },
    )

    assert create_event_response.status_code == 201
    event_payload = create_event_response.get_json()["event"]
    assert event_payload["status"] == "open"
    assert len(event_payload["outcomes"]) == 2
    assert event_payload["market_state"]["algorithm"] == "LMSR"
    assert event_payload["outcomes"][0]["probability_pct"] == "50.0"
    assert event_payload["outcomes"][1]["probability_pct"] == "50.0"

    prediction_response = client.post(
        f"/api/events/{event_payload['id']}/predictions",
        headers=headers,
        json={"outcome_id": event_payload["outcomes"][0]["id"], "stake_amount": "250.00"},
    )

    assert prediction_response.status_code == 201
    prediction_payload = prediction_response.get_json()["prediction"]
    assert prediction_payload["stake_amount"] == "250.00"
    assert float(prediction_payload["share_quantity"]) > 250.0
    assert float(prediction_payload["average_price"]) < 1.0
    post_trade_event = prediction_response.get_json()["event"]
    assert float(post_trade_event["outcomes"][0]["probability_pct"]) > 50.0
    assert float(post_trade_event["outcomes"][1]["probability_pct"]) < 50.0

    quote_response = client.post(
        f"/api/events/{event_payload['id']}/quote",
        headers=headers,
        json={"outcome_id": event_payload["outcomes"][1]["id"], "stake_amount": "100.00"},
    )
    assert quote_response.status_code == 200
    assert float(quote_response.get_json()["quote"]["share_quantity"]) > 0.0

    profile_response = client.get("/api/me", headers=headers)
    profile_payload = profile_response.get_json()
    assert profile_payload["wallet"]["current_balance"] == "9750.00"
    assert len(profile_payload["recent_predictions"]) == 1
    assert profile_payload["recent_predictions"][0]["event_title"] == "Will BTC close above $100k by end of 2026?"
    assert profile_payload["recent_predictions"][0]["outcome_label"] == "Yes"
    assert profile_payload["recent_created_events"][0]["title"] == "Will BTC close above $100k by end of 2026?"


def test_cannot_place_prediction_on_closed_event(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "late@example.com",
            "handle": "lateplayer",
            "password": "strong-pass-123",
        },
    )
    login_response = client.post(
        "/api/auth/login",
        json={"email": "late@example.com", "password": "strong-pass-123"},
    )
    token = login_response.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_event_response = client.post(
        "/api/events",
        headers=headers,
        json={
            "title": "Past close event",
            "description": "Should reject new predictions",
            "category": "politics",
            "source_of_truth": "Official source",
            "closes_at": "2025-01-01T00:00:00Z",
            "resolves_at": "2026-12-31T23:59:59Z",
            "outcomes": ["Yes", "No"],
        },
    )
    assert create_event_response.status_code == 400
    assert create_event_response.get_json()["error"] == "closes_at must be at least 5 minutes in the future."


def test_resolve_event_and_credit_winner(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "resolver@example.com",
            "handle": "resolver",
            "password": "strong-pass-123",
        },
    )
    login_response = client.post(
        "/api/auth/login",
        json={"email": "resolver@example.com", "password": "strong-pass-123"},
    )
    token = login_response.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_event_response = client.post(
        "/api/events",
        headers=headers,
        json={
            "title": "Will inflation fall this quarter?",
            "description": "Resolution flow test",
            "category": "macro",
            "source_of_truth": "Official statistics",
            "closes_at": "2026-06-01T00:00:00Z",
            "resolves_at": "2026-06-30T00:00:00Z",
            "outcomes": ["Yes", "No"],
        },
    )
    event_payload = create_event_response.get_json()["event"]

    prediction_response = client.post(
        f"/api/events/{event_payload['id']}/predictions",
        headers=headers,
        json={"outcome_id": event_payload["outcomes"][0]["id"], "stake_amount": "250.00"},
    )
    assert prediction_response.status_code == 201

    resolve_response = client.post(
        f"/api/events/{event_payload['id']}/resolve",
        headers=headers,
        json={"winning_outcome_id": event_payload["outcomes"][0]["id"]},
    )

    assert resolve_response.status_code == 200
    resolved_payload = resolve_response.get_json()["event"]
    assert resolved_payload["status"] == "resolved"
    assert resolved_payload["resolved_outcome_id"] == event_payload["outcomes"][0]["id"]

    profile_response = client.get("/api/me", headers=headers)
    profile_payload = profile_response.get_json()
    assert Decimal(profile_payload["wallet"]["current_balance"]) > Decimal("10000.00")
    assert profile_payload["recent_predictions"][0]["status"] == "won"



def test_buy_and_sell_asset_in_private_portfolio(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "portfolio@example.com",
            "handle": "portfolioguy",
            "password": "strong-pass-123",
        },
    )
    login_response = client.post(
        "/api/auth/login",
        json={"email": "portfolio@example.com", "password": "strong-pass-123"},
    )
    token = login_response.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    asset_response = client.post(
        "/api/assets",
        headers=headers,
        json={
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "asset_type": "stock",
            "current_price": "200.00",
        },
    )
    assert asset_response.status_code == 201
    asset_payload = asset_response.get_json()["asset"]

    buy_response = client.post(
        "/api/portfolio/trades",
        headers=headers,
        json={"asset_id": asset_payload["id"], "side": "buy", "quantity": "2"},
    )
    assert buy_response.status_code == 201
    assert buy_response.get_json()["trade"]["gross_amount"] == "400.00"

    portfolio_response = client.get("/api/portfolio/me", headers=headers)
    assert portfolio_response.status_code == 200
    portfolio_payload = portfolio_response.get_json()
    assert portfolio_payload["summary"]["available_cash"] == "9600.00"
    assert portfolio_payload["summary"]["market_value"] == "400.00"
    assert len(portfolio_payload["holdings"]) == 1
    assert portfolio_payload["holdings"][0]["symbol"] == "AAPL"

    price_update_response = client.patch(
        f"/api/assets/{asset_payload['id']}/price",
        headers=headers,
        json={"current_price": "250.00"},
    )
    assert price_update_response.status_code == 200

    sell_response = client.post(
        "/api/portfolio/trades",
        headers=headers,
        json={"asset_id": asset_payload["id"], "side": "sell", "quantity": "1"},
    )
    assert sell_response.status_code == 201
    assert sell_response.get_json()["trade"]["gross_amount"] == "250.00"

    updated_portfolio_response = client.get("/api/portfolio/me", headers=headers)
    updated_portfolio_payload = updated_portfolio_response.get_json()
    assert updated_portfolio_payload["summary"]["available_cash"] == "9850.00"
    assert updated_portfolio_payload["summary"]["realized_pnl"] == "50.00"
    assert updated_portfolio_payload["summary"]["market_value"] == "250.00"
    assert updated_portfolio_payload["holdings"][0]["quantity"] == "1.00000000"


def test_search_market_assets_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.portfolio.search_market_assets",
        lambda query, limit=8: [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "asset_type": "stock",
                "exchange": "NASDAQ",
                "sector": "Technology",
                "industry": "Consumer Electronics",
            }
        ],
    )

    response = client.get("/api/assets/search?q=apple")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["items"][0]["symbol"] == "AAPL"
    assert payload["items"][0]["asset_type"] == "stock"
    assert payload["items"][0]["local_asset_id"] is None


def test_buy_asset_by_symbol_creates_local_market_asset(client, monkeypatch):
    client.post(
        "/api/auth/register",
        json={
            "email": "symboltrade@example.com",
            "handle": "symboltrader",
            "password": "strong-pass-123",
        },
    )
    login_response = client.post(
        "/api/auth/login",
        json={"email": "symboltrade@example.com", "password": "strong-pass-123"},
    )
    token = login_response.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr(
        "app.services.portfolio_service.get_market_quote",
        lambda symbol, track=True: {
            "symbol": "BTC-USD",
            "name": "Bitcoin USD",
            "asset_type": "crypto",
            "currency": "USD",
            "exchange": "CCC",
            "current_price": "50000.00",
            "previous_close": "49500.00",
            "day_high": "50500.00",
            "day_low": "49000.00",
            "volume": "12345",
            "change": "500.00",
            "change_percent": "1.01",
            "source": "yahoo_chart",
        },
    )

    buy_response = client.post(
        "/api/portfolio/trades",
        headers=headers,
        json={"symbol": "BTC-USD", "side": "buy", "quantity": "0.1"},
    )

    assert buy_response.status_code == 201
    assert buy_response.get_json()["trade"]["symbol"] == "BTC-USD"
    assert buy_response.get_json()["trade"]["gross_amount"] == "5000.00"

    portfolio_response = client.get("/api/portfolio/me", headers=headers)
    assert portfolio_response.status_code == 200
    portfolio_payload = portfolio_response.get_json()
    assert portfolio_payload["summary"]["available_cash"] == "5000.00"
    assert portfolio_payload["holdings"][0]["symbol"] == "BTC-USD"
    assert portfolio_payload["holdings"][0]["asset_type"] == "crypto"

    assets_response = client.get("/api/assets")
    assert assets_response.status_code == 200
    assets_payload = assets_response.get_json()
    assert assets_payload["items"][0]["symbol"] == "BTC-USD"


def test_buy_asset_by_symbol_returns_400_when_balance_is_too_low(client, monkeypatch):
    client.post(
        "/api/auth/register",
        json={
            "email": "lowbalancecrypto@example.com",
            "handle": "lowbalancecrypto",
            "password": "strong-pass-123",
        },
    )
    login_response = client.post(
        "/api/auth/login",
        json={"email": "lowbalancecrypto@example.com", "password": "strong-pass-123"},
    )
    token = login_response.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    monkeypatch.setattr(
        "app.services.portfolio_service.get_market_quote",
        lambda symbol, track=True: {
            "symbol": "BTC-USD",
            "name": "Bitcoin USD",
            "asset_type": "crypto",
            "currency": "USD",
            "exchange": "CCC",
            "current_price": "70000.00",
            "previous_close": "69000.00",
            "day_high": "71000.00",
            "day_low": "68000.00",
            "volume": "12345",
            "change": "1000.00",
            "change_percent": "1.45",
            "source": "yahoo_chart",
        },
    )

    buy_response = client.post(
        "/api/portfolio/trades",
        headers=headers,
        json={"symbol": "BTC-USD", "side": "buy", "quantity": "1"},
    )

    assert buy_response.status_code == 400
    assert buy_response.get_json()["error"] == "Insufficient balance."


def test_portfolio_watchlist_persists_in_database(client, monkeypatch):
    client.post(
        "/api/auth/register",
        json={
            "email": "watchlist@example.com",
            "handle": "watchlistuser",
            "password": "strong-pass-123",
        },
    )
    login_response = client.post(
        "/api/auth/login",
        json={"email": "watchlist@example.com", "password": "strong-pass-123"},
    )
    headers = {"Authorization": f"Bearer {login_response.get_json()['access_token']}"}

    monkeypatch.setattr(
        "app.services.portfolio_service.get_market_quote",
        lambda symbol, track=True: {
            "symbol": str(symbol).upper(),
            "name": "Apple Inc.",
            "asset_type": "stock",
            "currency": "USD",
            "exchange": "NASDAQ",
            "current_price": "210.00",
            "previous_close": "205.00",
            "day_high": "211.00",
            "day_low": "204.00",
            "volume": "1000000",
            "change": "5.00",
            "change_percent": "2.44",
            "source": "yahoo_chart",
        },
    )

    add_response = client.post("/api/portfolio/watchlist", headers=headers, json={"symbol": "AAPL"})
    assert add_response.status_code == 201
    assert add_response.get_json()["asset"]["symbol"] == "AAPL"

    list_response = client.get("/api/portfolio/watchlist", headers=headers)
    assert list_response.status_code == 200
    items = list_response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["symbol"] == "AAPL"

    duplicate_response = client.post("/api/portfolio/watchlist", headers=headers, json={"symbol": "AAPL"})
    assert duplicate_response.status_code == 201

    list_again_response = client.get("/api/portfolio/watchlist", headers=headers)
    assert len(list_again_response.get_json()["items"]) == 1

    remove_response = client.delete("/api/portfolio/watchlist/AAPL", headers=headers)
    assert remove_response.status_code == 200

    final_list_response = client.get("/api/portfolio/watchlist", headers=headers)
    assert final_list_response.status_code == 200
    assert final_list_response.get_json()["items"] == []


def test_admin_can_credit_user_balance(client):
    client.post(
        "/api/auth/register",
        json={"email": "admincredit@example.com", "handle": "admincredit", "password": "strong-pass-123"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "wallettarget@example.com", "handle": "wallettarget", "password": "strong-pass-123"},
    )

    admin_login = client.post(
        "/api/auth/login",
        json={"email": "admincredit@example.com", "password": "strong-pass-123"},
    )
    user_login = client.post(
        "/api/auth/login",
        json={"email": "wallettarget@example.com", "password": "strong-pass-123"},
    )

    admin_headers = {"Authorization": f"Bearer {admin_login.get_json()['access_token']}"}
    user_headers = {"Authorization": f"Bearer {user_login.get_json()['access_token']}"}

    users_response = client.get("/api/admin/users", headers=admin_headers)
    assert users_response.status_code == 200
    target_user = next(item for item in users_response.get_json()["items"] if item["handle"] == "wallettarget")
    assert target_user["wallet_balance"] == "10000.00"

    credit_response = client.post(
        f"/api/admin/users/{target_user['id']}/wallet-credit",
        headers=admin_headers,
        json={"amount": "2500.00", "note": "manual support top up"},
    )
    assert credit_response.status_code == 200
    credit_payload = credit_response.get_json()
    assert credit_payload["wallet_entry"]["amount"] == "2500.00"
    assert credit_payload["user"]["wallet_balance"] == "12500.00"

    me_response = client.get("/api/me", headers=user_headers)
    assert me_response.status_code == 200
    assert me_response.get_json()["wallet"]["current_balance"] == "12500.00"


def test_public_portfolio_summary_hides_holdings(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "publicportfolio@example.com",
            "handle": "publicalpha",
            "password": "strong-pass-123",
        },
    )
    login_response = client.post(
        "/api/auth/login",
        json={"email": "publicportfolio@example.com", "password": "strong-pass-123"},
    )
    token = login_response.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    asset_response = client.post(
        "/api/assets",
        headers=headers,
        json={
            "symbol": "MSFT",
            "name": "Microsoft",
            "asset_type": "stock",
            "current_price": "300.00",
        },
    )
    asset_payload = asset_response.get_json()["asset"]
    client.post(
        "/api/portfolio/trades",
        headers=headers,
        json={"asset_id": asset_payload["id"], "side": "buy", "quantity": "1"},
    )

    public_summary_response = client.get("/api/users/publicalpha/portfolio-summary")
    assert public_summary_response.status_code == 200
    public_summary = public_summary_response.get_json()["summary"]
    assert public_summary["handle"] == "publicalpha"
    assert public_summary["market_value"] == "300.00"
    assert "holdings" not in public_summary
    assert "recent_trades" not in public_summary


def test_prediction_leaderboard_ranks_winner_above_loser(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "winner@example.com",
            "handle": "winner",
            "password": "strong-pass-123",
        },
    )
    client.post(
        "/api/auth/register",
        json={
            "email": "loser@example.com",
            "handle": "loser",
            "password": "strong-pass-123",
        },
    )

    winner_login = client.post(
        "/api/auth/login",
        json={"email": "winner@example.com", "password": "strong-pass-123"},
    )
    loser_login = client.post(
        "/api/auth/login",
        json={"email": "loser@example.com", "password": "strong-pass-123"},
    )
    winner_headers = {"Authorization": f"Bearer {winner_login.get_json()['access_token']}"}
    loser_headers = {"Authorization": f"Bearer {loser_login.get_json()['access_token']}"}

    create_event_response = client.post(
        "/api/events",
        headers=winner_headers,
        json={
            "title": "Will EUR/USD end the week above 1.10?",
            "description": "Leaderboard test",
            "category": "fx",
            "source_of_truth": "ECB reference rate",
            "closes_at": "2026-07-01T00:00:00Z",
            "resolves_at": "2026-07-02T00:00:00Z",
            "outcomes": ["Yes", "No"],
        },
    )
    event_payload = create_event_response.get_json()["event"]
    yes_outcome = event_payload["outcomes"][0]["id"]
    no_outcome = event_payload["outcomes"][1]["id"]

    client.post(
        f"/api/events/{event_payload['id']}/predictions",
        headers=winner_headers,
        json={"outcome_id": yes_outcome, "stake_amount": "300.00"},
    )
    client.post(
        f"/api/events/{event_payload['id']}/predictions",
        headers=loser_headers,
        json={"outcome_id": no_outcome, "stake_amount": "300.00"},
    )
    client.post(
        f"/api/events/{event_payload['id']}/resolve",
        headers=winner_headers,
        json={"winning_outcome_id": yes_outcome},
    )

    leaderboard_response = client.get("/api/leaderboards/predictions?refresh=true")
    assert leaderboard_response.status_code == 200
    leaderboard_payload = leaderboard_response.get_json()
    assert leaderboard_payload["items"][0]["handle"] == "winner"
    assert leaderboard_payload["items"][0]["rank"] == 1
    assert leaderboard_payload["items"][1]["handle"] == "loser"
    assert leaderboard_payload["items"][1]["rank"] == 2


def test_portfolio_leaderboard_ranks_higher_return_first(client):
    client.post(
        "/api/auth/register",
        json={
            "email": "alpha@example.com",
            "handle": "alpha",
            "password": "strong-pass-123",
        },
    )
    client.post(
        "/api/auth/register",
        json={
            "email": "beta@example.com",
            "handle": "beta",
            "password": "strong-pass-123",
        },
    )

    alpha_login = client.post(
        "/api/auth/login",
        json={"email": "alpha@example.com", "password": "strong-pass-123"},
    )
    beta_login = client.post(
        "/api/auth/login",
        json={"email": "beta@example.com", "password": "strong-pass-123"},
    )
    alpha_headers = {"Authorization": f"Bearer {alpha_login.get_json()['access_token']}"}
    beta_headers = {"Authorization": f"Bearer {beta_login.get_json()['access_token']}"}

    asset_response = client.post(
        "/api/assets",
        headers=alpha_headers,
        json={
            "symbol": "NVDA",
            "name": "NVIDIA",
            "asset_type": "stock",
            "current_price": "100.00",
        },
    )
    asset_id = asset_response.get_json()["asset"]["id"]

    client.post(
        "/api/portfolio/trades",
        headers=alpha_headers,
        json={"asset_id": asset_id, "side": "buy", "quantity": "5"},
    )
    client.patch(
        f"/api/assets/{asset_id}/price",
        headers=alpha_headers,
        json={"current_price": "150.00"},
    )
    client.post(
        "/api/portfolio/trades",
        headers=beta_headers,
        json={"asset_id": asset_id, "side": "buy", "quantity": "2"},
    )

    leaderboard_response = client.get("/api/leaderboards/portfolios?refresh=true")
    assert leaderboard_response.status_code == 200
    leaderboard_payload = leaderboard_response.get_json()
    assert leaderboard_payload["items"][0]["handle"] == "alpha"
    assert leaderboard_payload["items"][0]["rank"] == 1
    assert leaderboard_payload["items"][1]["handle"] == "beta"
    assert leaderboard_payload["items"][1]["rank"] == 2
    assert "holdings" not in leaderboard_payload["items"][0]


def test_follow_and_activity_feed_show_followed_predictions(client):
    client.post(
        "/api/auth/register",
        json={"email": "alice@example.com", "handle": "alice", "password": "strong-pass-123"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "handle": "bob", "password": "strong-pass-123"},
    )

    alice_login = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "strong-pass-123"})
    bob_login = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "strong-pass-123"})
    alice_headers = {"Authorization": f"Bearer {alice_login.get_json()['access_token']}"}
    bob_headers = {"Authorization": f"Bearer {bob_login.get_json()['access_token']}"}

    follow_response = client.post("/api/users/bob/follow", headers=alice_headers)
    assert follow_response.status_code == 201

    create_event_response = client.post(
        "/api/events",
        headers=bob_headers,
        json={
            "title": "Will gold finish the month higher?",
            "description": "Social feed test",
            "category": "commodities",
            "source_of_truth": "LBMA",
            "closes_at": "2026-08-01T00:00:00Z",
            "resolves_at": "2026-08-02T00:00:00Z",
            "outcomes": ["Yes", "No"],
        },
    )
    event_payload = create_event_response.get_json()["event"]
    assert event_payload["status"] == "pending_review"

    moderate_response = client.post(
        f"/api/admin/events/{event_payload['id']}/moderate",
        headers=alice_headers,
        json={"decision": "approve", "notes": "Looks acceptable."},
    )
    assert moderate_response.status_code == 200

    prediction_response = client.post(
        f"/api/events/{event_payload['id']}/predictions",
        headers=bob_headers,
        json={"outcome_id": event_payload["outcomes"][0]["id"], "stake_amount": "150.00"},
    )
    assert prediction_response.status_code == 201

    feed_response = client.get("/api/social/feed", headers=alice_headers)
    assert feed_response.status_code == 200
    feed_payload = feed_response.get_json()
    assert len(feed_payload["items"]) >= 2
    assert {item["type"] for item in feed_payload["items"]} >= {"event", "prediction"}

    prediction_item = next(item for item in feed_payload["items"] if item["type"] == "prediction")
    assert prediction_item["handle"] == "bob"
    assert prediction_item["stake_amount"] == "150.00"

    event_item = next(item for item in feed_payload["items"] if item["type"] == "event")
    assert event_item["handle"] == "bob"
    assert event_item["event_title"] == "Will gold finish the month higher?"


def test_social_discovery_returns_following_and_suggestions(client):
    client.post(
        "/api/auth/register",
        json={"email": "viewer@example.com", "handle": "viewer", "password": "strong-pass-123"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "maker@example.com", "handle": "maker", "password": "strong-pass-123"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "creator@example.com", "handle": "creator", "password": "strong-pass-123"},
    )

    viewer_login = client.post("/api/auth/login", json={"email": "viewer@example.com", "password": "strong-pass-123"})
    maker_login = client.post("/api/auth/login", json={"email": "maker@example.com", "password": "strong-pass-123"})
    creator_login = client.post("/api/auth/login", json={"email": "creator@example.com", "password": "strong-pass-123"})
    viewer_headers = {"Authorization": f"Bearer {viewer_login.get_json()['access_token']}"}
    maker_headers = {"Authorization": f"Bearer {maker_login.get_json()['access_token']}"}
    creator_headers = {"Authorization": f"Bearer {creator_login.get_json()['access_token']}"}

    assert client.post("/api/users/maker/follow", headers=viewer_headers).status_code == 201

    create_event_response = client.post(
        "/api/events",
        headers=creator_headers,
        json={
            "title": "Will EURUSD hold above 1.10?",
            "description": "Discovery creator test",
            "category": "forex",
            "source_of_truth": "ECB",
            "closes_at": "2026-10-01T00:00:00Z",
            "resolves_at": "2026-10-02T00:00:00Z",
            "outcomes": ["Yes", "No"],
        },
    )
    event_payload = create_event_response.get_json()["event"]
    assert create_event_response.status_code == 201

    moderate_response = client.post(
        f"/api/admin/events/{event_payload['id']}/moderate",
        headers=viewer_headers,
        json={"decision": "approve", "notes": "Discovery setup"},
    )
    assert moderate_response.status_code == 200

    discovery_response = client.get("/api/social/discovery", headers=viewer_headers)
    assert discovery_response.status_code == 200
    payload = discovery_response.get_json()
    assert any(item["handle"] == "maker" for item in payload["following"])
    assert any(item["handle"] == "creator" for item in payload["recommended_users"])


def test_follow_creates_social_inbox_notification_and_can_mark_read(client):
    client.post(
        "/api/auth/register",
        json={"email": "reader@example.com", "handle": "reader", "password": "strong-pass-123"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "author@example.com", "handle": "author", "password": "strong-pass-123"},
    )

    reader_login = client.post("/api/auth/login", json={"email": "reader@example.com", "password": "strong-pass-123"})
    author_login = client.post("/api/auth/login", json={"email": "author@example.com", "password": "strong-pass-123"})
    reader_headers = {"Authorization": f"Bearer {reader_login.get_json()['access_token']}"}
    author_headers = {"Authorization": f"Bearer {author_login.get_json()['access_token']}"}

    follow_response = client.post("/api/users/author/follow", headers=reader_headers)
    assert follow_response.status_code == 201

    inbox_response = client.get("/api/social/inbox", headers=author_headers)
    assert inbox_response.status_code == 200
    inbox_items = inbox_response.get_json()["items"]
    assert len(inbox_items) == 1
    assert inbox_items[0]["notification_type"] == "new_follower"
    assert inbox_items[0]["actor_handle"] == "reader"
    assert inbox_items[0]["is_read"] is False

    read_response = client.post(f"/api/social/inbox/{inbox_items[0]['id']}/read", headers=author_headers)
    assert read_response.status_code == 200
    assert read_response.get_json()["notification"]["is_read"] is True

    me_response = client.get("/api/me", headers=author_headers)
    assert me_response.status_code == 200
    assert me_response.get_json()["social"]["unread_notifications_count"] == 0


def test_event_approval_populates_social_inbox_for_creator_and_followers(client):
    client.post(
        "/api/auth/register",
        json={"email": "adminsocial@example.com", "handle": "adminsocial", "password": "strong-pass-123"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "maker2@example.com", "handle": "maker2", "password": "strong-pass-123"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "follower2@example.com", "handle": "follower2", "password": "strong-pass-123"},
    )

    admin_login = client.post("/api/auth/login", json={"email": "adminsocial@example.com", "password": "strong-pass-123"})
    maker_login = client.post("/api/auth/login", json={"email": "maker2@example.com", "password": "strong-pass-123"})
    follower_login = client.post("/api/auth/login", json={"email": "follower2@example.com", "password": "strong-pass-123"})
    admin_headers = {"Authorization": f"Bearer {admin_login.get_json()['access_token']}"}
    maker_headers = {"Authorization": f"Bearer {maker_login.get_json()['access_token']}"}
    follower_headers = {"Authorization": f"Bearer {follower_login.get_json()['access_token']}"}

    assert client.post("/api/users/maker2/follow", headers=follower_headers).status_code == 201

    create_event_response = client.post(
        "/api/events",
        headers=maker_headers,
        json={
            "title": "Will Nvidia close the quarter green?",
            "description": "Inbox moderation test",
            "category": "stocks",
            "source_of_truth": "Nasdaq close",
            "closes_at": "2026-11-01T00:00:00Z",
            "resolves_at": "2026-11-02T00:00:00Z",
            "outcomes": ["Yes", "No"],
        },
    )
    assert create_event_response.status_code == 201
    event_payload = create_event_response.get_json()["event"]
    assert event_payload["status"] == "pending_review"

    moderate_response = client.post(
        f"/api/admin/events/{event_payload['id']}/moderate",
        headers=admin_headers,
        json={"decision": "approve", "notes": "Looks good."},
    )
    assert moderate_response.status_code == 200

    creator_inbox = client.get("/api/social/inbox", headers=maker_headers)
    assert creator_inbox.status_code == 200
    creator_items = creator_inbox.get_json()["items"]
    assert any(item["notification_type"] == "event_moderated" for item in creator_items)

    follower_inbox = client.get("/api/social/inbox", headers=follower_headers)
    assert follower_inbox.status_code == 200
    follower_items = follower_inbox.get_json()["items"]
    published_item = next(item for item in follower_items if item["notification_type"] == "followed_user_event_published")
    assert published_item["actor_handle"] == "maker2"
    assert published_item["payload"]["event_title"] == "Will Nvidia close the quarter green?"

    read_all_response = client.post("/api/social/inbox/read-all", headers=follower_headers)
    assert read_all_response.status_code == 200
    assert read_all_response.get_json()["updated"] >= 1


def test_public_profile_shows_counts_and_hides_private_portfolio_data(client):
    client.post(
        "/api/auth/register",
        json={"email": "profile@example.com", "handle": "profileuser", "password": "strong-pass-123"},
    )
    login_response = client.post(
        "/api/auth/login",
        json={"email": "profile@example.com", "password": "strong-pass-123"},
    )
    headers = {"Authorization": f"Bearer {login_response.get_json()['access_token']}"}

    asset_response = client.post(
        "/api/assets",
        headers=headers,
        json={"symbol": "AMZN", "name": "Amazon", "asset_type": "stock", "current_price": "100.00"},
    )
    asset_id = asset_response.get_json()["asset"]["id"]
    client.post(
        "/api/portfolio/trades",
        headers=headers,
        json={"asset_id": asset_id, "side": "buy", "quantity": "2"},
    )

    profile_response = client.get("/api/users/profileuser")
    assert profile_response.status_code == 200
    profile_payload = profile_response.get_json()["profile"]
    assert profile_payload["handle"] == "profileuser"
    assert profile_payload["followers_count"] == 0
    assert profile_payload["following_count"] == 0
    assert profile_payload["approved_events_count"] == 0
    assert profile_payload["resolved_events_count"] == 0
    assert "holdings" not in profile_payload["portfolio_summary"]
    assert "available_cash" not in profile_payload["portfolio_summary"]


def test_unfollow_removes_feed_visibility(client):
    client.post(
        "/api/auth/register",
        json={"email": "follower@example.com", "handle": "follower", "password": "strong-pass-123"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "followee@example.com", "handle": "followee", "password": "strong-pass-123"},
    )

    follower_login = client.post("/api/auth/login", json={"email": "follower@example.com", "password": "strong-pass-123"})
    followee_login = client.post("/api/auth/login", json={"email": "followee@example.com", "password": "strong-pass-123"})
    follower_headers = {"Authorization": f"Bearer {follower_login.get_json()['access_token']}"}
    followee_headers = {"Authorization": f"Bearer {followee_login.get_json()['access_token']}"}

    client.post("/api/users/followee/follow", headers=follower_headers)
    client.delete("/api/users/followee/follow", headers=follower_headers)

    create_event_response = client.post(
        "/api/events",
        headers=followee_headers,
        json={
            "title": "Will oil close above 90?",
            "description": "Unfollow visibility test",
            "category": "energy",
            "source_of_truth": "ICE",
            "closes_at": "2026-09-01T00:00:00Z",
            "resolves_at": "2026-09-02T00:00:00Z",
            "outcomes": ["Yes", "No"],
        },
    )
    event_payload = create_event_response.get_json()["event"]
    client.post(
        f"/api/events/{event_payload['id']}/predictions",
        headers=followee_headers,
        json={"outcome_id": event_payload["outcomes"][0]["id"], "stake_amount": "120.00"},
    )

    feed_response = client.get("/api/social/feed", headers=follower_headers)
    assert feed_response.status_code == 200
    assert feed_response.get_json()["items"] == []


def test_registration_assigns_free_subscription_and_entitlements(client):
    register_response = client.post(
        "/api/auth/register",
        json={"email": "billing@example.com", "handle": "billinguser", "password": "strong-pass-123"},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/auth/login",
        json={"email": "billing@example.com", "password": "strong-pass-123"},
    )
    headers = {"Authorization": f"Bearer {login_response.get_json()['access_token']}"}

    me_response = client.get("/api/me", headers=headers)
    assert me_response.status_code == 200
    me_payload = me_response.get_json()
    assert me_payload["subscription"]["plan"]["code"] == "free"
    assert me_payload["entitlements"]["max_follows"] == 3
    assert me_payload["entitlements"]["advanced_analytics"] is False


def test_billing_plans_checkout_and_webhook_upgrade_to_pro(client):
    client.post(
        "/api/auth/register",
        json={"email": "upgrade@example.com", "handle": "upgradeuser", "password": "strong-pass-123"},
    )
    login_response = client.post(
        "/api/auth/login",
        json={"email": "upgrade@example.com", "password": "strong-pass-123"},
    )
    headers = {"Authorization": f"Bearer {login_response.get_json()['access_token']}"}

    plans_response = client.get("/api/billing/plans")
    assert plans_response.status_code == 200
    plans_payload = plans_response.get_json()["items"]
    assert [plan["code"] for plan in plans_payload] == ["free", "pro", "elite"]

    checkout_response = client.post(
        "/api/billing/checkout-session",
        headers=headers,
        json={"plan_code": "pro"},
    )
    assert checkout_response.status_code == 201
    checkout_payload = checkout_response.get_json()["checkout_session"]
    assert checkout_payload["plan_code"] == "pro"
    assert checkout_payload["provider"] in {"mock", "stripe"}

    webhook_response = client.post(
        "/api/billing/webhooks/stripe",
        json={
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_test_123",
                    "subscription": "sub_test_123",
                    "metadata": {"user_id": "1", "plan_code": "pro"},
                }
            },
        },
    )
    assert webhook_response.status_code == 200
    assert webhook_response.get_json()["subscription"]["plan"]["code"] == "pro"

    billing_me_response = client.get("/api/billing/me", headers=headers)
    assert billing_me_response.status_code == 200
    billing_me_payload = billing_me_response.get_json()["subscription"]
    assert billing_me_payload["plan"]["code"] == "pro"
    assert billing_me_payload["plan"]["entitlements"]["advanced_analytics"] is True


def test_follow_limit_gating_changes_after_upgrade(client):
    client.post(
        "/api/auth/register",
        json={"email": "limit@example.com", "handle": "limituser", "password": "strong-pass-123"},
    )
    login_response = client.post(
        "/api/auth/login",
        json={"email": "limit@example.com", "password": "strong-pass-123"},
    )
    headers = {"Authorization": f"Bearer {login_response.get_json()['access_token']}"}

    for handle in ["u1", "u2", "u3", "u4"]:
        client.post(
            "/api/auth/register",
            json={"email": f"{handle}@example.com", "handle": handle, "password": "strong-pass-123"},
        )

    assert client.post("/api/users/u1/follow", headers=headers).status_code == 201
    assert client.post("/api/users/u2/follow", headers=headers).status_code == 201
    assert client.post("/api/users/u3/follow", headers=headers).status_code == 201

    blocked_response = client.post("/api/users/u4/follow", headers=headers)
    assert blocked_response.status_code == 400
    assert blocked_response.get_json()["error"] == "Follow limit reached for your current plan."

    upgrade_response = client.post(
        "/api/billing/webhooks/stripe",
        json={
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_test_999",
                    "subscription": "sub_test_999",
                    "metadata": {"user_id": "1", "plan_code": "pro"},
                }
            },
        },
    )
    assert upgrade_response.status_code == 200

    allowed_response = client.post("/api/users/u4/follow", headers=headers)
    assert allowed_response.status_code == 201


def test_register_verify_email_and_refresh_token_flow(client):
    register_response = client.post(
        "/api/auth/register",
        json={"email": "verify@example.com", "handle": "verifyuser", "password": "strong-pass-123"},
    )
    assert register_response.status_code == 201
    verification_token = register_response.get_json()["dev_notes"]["email_verification_token"]

    verify_response = client.post("/api/auth/verify-email", json={"token": verification_token})
    assert verify_response.status_code == 200
    assert verify_response.get_json()["user"]["email_verified"] is True
    assert verify_response.get_json()["user"]["verification_status"] == "email_verified"

    login_response = client.post(
        "/api/auth/login",
        json={"email": "verify@example.com", "password": "strong-pass-123"},
    )
    assert login_response.status_code == 200
    refresh_token = login_response.get_json()["refresh_token"]

    refresh_response = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert refresh_response.status_code == 200
    assert refresh_response.get_json()["access_token"]


def test_failed_logins_mark_account_suspicious(client):
    client.post(
        "/api/auth/register",
        json={"email": "suspicious@example.com", "handle": "suspicioususer", "password": "strong-pass-123"},
    )

    for _ in range(5):
        failed_response = client.post(
            "/api/auth/login",
            json={"email": "suspicious@example.com", "password": "wrong-pass"},
        )
        assert failed_response.status_code == 401

    login_response = client.post(
        "/api/auth/login",
        json={"email": "suspicious@example.com", "password": "strong-pass-123"},
    )
    assert login_response.status_code == 200
    headers = {"Authorization": f"Bearer {login_response.get_json()['access_token']}"}

    me_response = client.get("/api/me", headers=headers)
    me_payload = me_response.get_json()
    assert me_payload["account_flags"]["suspicious_activity"] is True
    assert me_payload["account_flags"]["failed_login_attempts"] == 0


def test_non_admin_events_require_admin_moderation_before_public_listing(client):
    client.post(
        "/api/auth/register",
        json={"email": "adminmod@example.com", "handle": "adminmod", "password": "strong-pass-123"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "creator@example.com", "handle": "creator", "password": "strong-pass-123"},
    )

    admin_login = client.post(
        "/api/auth/login",
        json={"email": "adminmod@example.com", "password": "strong-pass-123"},
    )
    creator_login = client.post(
        "/api/auth/login",
        json={"email": "creator@example.com", "password": "strong-pass-123"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.get_json()['access_token']}"}
    creator_headers = {"Authorization": f"Bearer {creator_login.get_json()['access_token']}"}

    create_event_response = client.post(
        "/api/events",
        headers=creator_headers,
        json={
            "title": "Will CPI print below consensus?",
            "description": "Moderation queue test",
            "category": "macro",
            "source_of_truth": "Official statistics",
            "closes_at": "2026-11-01T00:00:00Z",
            "resolves_at": "2026-11-02T00:00:00Z",
            "outcomes": ["Yes", "No"],
        },
    )

    assert create_event_response.status_code == 201
    event_payload = create_event_response.get_json()["event"]
    assert event_payload["status"] == "pending_review"

    public_events_before = client.get("/api/events")
    assert all(item["id"] != event_payload["id"] for item in public_events_before.get_json()["items"])

    dashboard_response = client.get("/api/admin/dashboard", headers=admin_headers)
    assert dashboard_response.status_code == 200
    assert dashboard_response.get_json()["pending_events"] >= 1

    pending_response = client.get("/api/admin/events/pending", headers=admin_headers)
    assert pending_response.status_code == 200
    assert pending_response.get_json()["items"][0]["id"] == event_payload["id"]

    approve_response = client.post(
        f"/api/admin/events/{event_payload['id']}/moderate",
        headers=admin_headers,
        json={"decision": "approve", "notes": "Within platform rules."},
    )
    assert approve_response.status_code == 200
    assert approve_response.get_json()["event"]["status"] == "open"
    assert approve_response.get_json()["event"]["title"] == "Will CPI print below consensus?"

    creator_profile_response = client.get("/api/me", headers=creator_headers)
    assert creator_profile_response.status_code == 200
    assert creator_profile_response.get_json()["recent_created_events"][0]["status"] == "open"

    public_events_after = client.get("/api/events")
    assert any(item["id"] == event_payload["id"] for item in public_events_after.get_json()["items"])


def test_admin_can_reject_pending_event(client):
    client.post(
        "/api/auth/register",
        json={"email": "adminreject@example.com", "handle": "adminreject", "password": "strong-pass-123"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "rejectme@example.com", "handle": "rejectme", "password": "strong-pass-123"},
    )

    admin_login = client.post(
        "/api/auth/login",
        json={"email": "adminreject@example.com", "password": "strong-pass-123"},
    )
    creator_login = client.post(
        "/api/auth/login",
        json={"email": "rejectme@example.com", "password": "strong-pass-123"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.get_json()['access_token']}"}
    creator_headers = {"Authorization": f"Bearer {creator_login.get_json()['access_token']}"}

    create_event_response = client.post(
        "/api/events",
        headers=creator_headers,
        json={
            "title": "Clearly bad market",
            "description": "Reject moderation test",
            "category": "other",
            "source_of_truth": "Unknown",
            "closes_at": "2026-10-01T00:00:00Z",
            "resolves_at": "2026-10-02T00:00:00Z",
            "outcomes": ["Yes", "No"],
        },
    )
    event_payload = create_event_response.get_json()["event"]

    reject_response = client.post(
        f"/api/admin/events/{event_payload['id']}/moderate",
        headers=admin_headers,
        json={"decision": "reject", "notes": "Out of policy scope."},
    )
    assert reject_response.status_code == 200
    assert reject_response.get_json()["event"]["status"] == "rejected"

    public_events = client.get("/api/events")
    assert all(item["id"] != event_payload["id"] for item in public_events.get_json()["items"])

    def test_admin_can_request_ai_event_generation(client, monkeypatch):
        client.post(
            "/api/auth/register",
            json={"email": "aigen@example.com", "handle": "aigenadmin", "password": "strong-pass-123"},
        )

        admin_login = client.post(
            "/api/auth/login",
            json={"email": "aigen@example.com", "password": "strong-pass-123"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.get_json()['access_token']}"}

        def fake_generate_ai_event_batch(**kwargs):
            assert kwargs["count"] == 2
            assert kwargs["publish_generated"] is False
            return {
                "used_model": "gpt-5-mini",
                "publish_generated": False,
                "create_seed_predictions": False,
                "source_briefs": [{"url": "https://example.com", "snippet": "source snippet"}],
                "warnings": ["Failed to fetch source URL https://example.com: HTTP Error 401: HTTP Forbidden"],
                "items": [
                    {
                        "title": "Will CPI print below 3%?",
                        "description": "Macro candidate",
                        "category": "macro",
                        "source_of_truth": "Official statistics release",
                        "outcomes": ["Yes", "No"],
                        "closes_at": "2026-12-01T00:00:00+00:00",
                        "resolves_at": "2026-12-02T00:00:00+00:00",
                        "confidence": 0.74,
                        "rationale": "Scheduled release with broad interest.",
                        "selection_reason": "Clear macro catalyst.",
                        "recommended_outcome": "Yes",
                        "recommended_stake": "40.00",
                        "publication_status": "suggested",
                        "event_id": None,
                        "seed_prediction": None,
                    }
                ],
            }

        monkeypatch.setattr("app.api.admin.generate_ai_event_batch", fake_generate_ai_event_batch)

        response = client.post(
            "/api/admin/ai/generate-events",
            headers=admin_headers,
            json={
                "count": 2,
                "topics": "CPI, Fed",
                "source_urls": ["https://example.com"],
                "source_notes": ["Next CPI release is scheduled for next week."],
                "publish_generated": False,
                "create_seed_predictions": False,
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["used_model"] == "gpt-5-mini"
        assert payload["items"][0]["title"] == "Will CPI print below 3%?"
        assert payload["warnings"][0].startswith("Failed to fetch source URL")


    def test_ai_generated_published_events_enter_pending_review(client, monkeypatch):
        client.post(
            "/api/auth/register",
            json={"email": "aiqueue@example.com", "handle": "aiqueueadmin", "password": "strong-pass-123"},
        )

        admin_login = client.post(
            "/api/auth/login",
            json={"email": "aiqueue@example.com", "password": "strong-pass-123"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.get_json()['access_token']}"}

        def fake_generate_ai_event_batch(**_kwargs):
            return {
                "used_model": "gpt-5-mini",
                "publish_generated": True,
                "create_seed_predictions": False,
                "source_briefs": [{"url": "operator-note-1", "snippet": "macro note"}],
                "warnings": [],
                "items": [
                    {
                        "title": "Will the next CPI print come below 3.0%?",
                        "description": "Macro queue candidate",
                        "category": "macro",
                        "source_of_truth": "BLS official CPI release",
                        "outcomes": ["Yes", "No"],
                        "closes_at": "2026-12-01T00:00:00+00:00",
                        "resolves_at": "2026-12-02T00:00:00+00:00",
                        "confidence": 0.7,
                        "rationale": "Clear macro release.",
                        "selection_reason": "Good first market.",
                        "recommended_outcome": "Yes",
                        "recommended_stake": "40.00",
                        "publication_status": "queued_for_review",
                        "event_id": 123,
                        "event_status": "pending_review",
                        "seed_prediction": {"status": "skipped", "reason": "Seed prediction skipped until the event passes admin moderation."},
                    }
                ],
            }

        monkeypatch.setattr("app.api.admin.generate_ai_event_batch", fake_generate_ai_event_batch)

        response = client.post(
            "/api/admin/ai/generate-events",
            headers=admin_headers,
            json={
                "count": 1,
                "topics": "CPI",
                "source_notes": ["Next CPI release is next week."],
                "publish_generated": True,
                "create_seed_predictions": False,
            },
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["items"][0]["publication_status"] == "queued_for_review"
        assert payload["items"][0]["event_status"] == "pending_review"
        assert payload["items"][0]["publication_status"] == "suggested"





