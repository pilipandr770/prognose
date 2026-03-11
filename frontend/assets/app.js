const state = {
  apiBase: localStorage.getItem("prognose.apiBase") || "/api",
  accessToken: localStorage.getItem("prognose.accessToken") || "",
  refreshToken: localStorage.getItem("prognose.refreshToken") || "",
  lastVerificationToken: localStorage.getItem("prognose.emailToken") || "",
  recentPredictions: [],
  portfolioMarket: {
    searchQuery: "",
    searchResults: [],
    selectedAsset: null,
    watchlist: [],
  },
  positionFilters: {
    query: "",
    status: "all",
  },
};

const currentPage = document.body.dataset.page || "landing";
const protectedPages = new Set(["dashboard", "events", "portfolio", "leaderboards", "social", "billing", "admin"]);

const els = {
  apiBase: document.getElementById("api-base"),
  frontendOrigin: document.getElementById("frontend-origin"),
  accountMetrics: document.getElementById("account-metrics"),
  accountJson: document.getElementById("account-json"),
  eventsList: document.getElementById("events-list"),
  assetsList: document.getElementById("assets-list"),
  portfolioMetrics: document.getElementById("portfolio-metrics"),
  portfolioJson: document.getElementById("portfolio-json"),
  portfolioHoldings: document.getElementById("portfolio-holdings"),
  portfolioTrades: document.getElementById("portfolio-trades"),
  portfolioSearchForm: document.getElementById("portfolio-search-form"),
  portfolioSearchQuery: document.getElementById("portfolio-search-query"),
  portfolioSearchResults: document.getElementById("portfolio-search-results"),
  marketFocus: document.getElementById("market-focus"),
  marketFocusNotice: document.getElementById("market-focus-notice"),
  predictionBoard: document.getElementById("prediction-board"),
  portfolioBoard: document.getElementById("portfolio-board"),
  feedList: document.getElementById("feed-list"),
  publicProfileJson: document.getElementById("public-profile-json"),
  plansGrid: document.getElementById("plans-grid"),
  activityLog: document.getElementById("activity-log"),
  adminMetrics: document.getElementById("admin-metrics"),
  adminUsersList: document.getElementById("admin-users-list"),
  adminUsersFeedback: document.getElementById("admin-users-feedback"),
  adminEventsList: document.getElementById("admin-events-list"),
  adminPendingEventsList: document.getElementById("admin-pending-events-list"),
  adminAiResults: document.getElementById("admin-ai-results"),
  billingMetrics: document.getElementById("billing-metrics"),
  billingJson: document.getElementById("billing-json"),
  eventsFeedback: document.getElementById("events-feedback"),
  myPositionsList: document.getElementById("my-positions-list"),
  myCreatedEventsList: document.getElementById("my-created-events-list"),
  positionsSearch: document.getElementById("positions-search"),
  positionsStatusFilter: document.getElementById("positions-status-filter"),
  adminFeedback: document.getElementById("admin-feedback"),
  adminAiFeedback: document.getElementById("admin-ai-feedback"),
};

const eventQuoteTimers = new Map();
const eventQuoteRequestSeq = new Map();
let portfolioSearchDebounceTimer = 0;
let portfolioMarketRefreshTimer = 0;

function byId(id) {
  return document.getElementById(id);
}

function bind(id, eventName, handler) {
  const element = byId(id);
  if (element) {
    element.addEventListener(eventName, handler);
  }
  return element;
}

function toggleAdminLinks(isAdmin) {
  document.querySelectorAll(".requires-admin").forEach((element) => {
    element.classList.toggle("is-hidden", !isAdmin);
  });
}

function clearSession() {
  state.accessToken = "";
  state.refreshToken = "";
  localStorage.removeItem("prognose.accessToken");
  localStorage.removeItem("prognose.refreshToken");
}

function redirectToLogin() {
  window.location.href = "/login";
}

function ensureAccess() {
  if (protectedPages.has(currentPage) && !state.accessToken) {
    redirectToLogin();
    return false;
  }
  return true;
}

function logResult(label, payload) {
  if (!els.activityLog) {
    return;
  }
  const line = `[${new Date().toLocaleTimeString()}] ${label}\n${JSON.stringify(payload, null, 2)}\n\n`;
  const previous = els.activityLog.textContent === "Лог пока пуст." ? "" : els.activityLog.textContent;
  els.activityLog.textContent = line + previous;
}

function setApiBase(value) {
  state.apiBase = value || "/api";
  localStorage.setItem("prognose.apiBase", state.apiBase);
  if (els.apiBase) {
    els.apiBase.value = state.apiBase;
  }
}

function saveTokens(accessToken, refreshToken) {
  if (accessToken) {
    state.accessToken = accessToken;
    localStorage.setItem("prognose.accessToken", accessToken);
  }
  if (refreshToken) {
    state.refreshToken = refreshToken;
    localStorage.setItem("prognose.refreshToken", refreshToken);
  }
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.accessToken && !options.skipAuth) {
    headers.Authorization = `Bearer ${state.accessToken}`;
  }

  const response = await fetch(`${state.apiBase}${path}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && !options.skipAuth) {
      clearSession();
      redirectToLogin();
    }
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function renderMetricCards(container, items) {
  if (!container) {
    return;
  }
  container.innerHTML = items
    .map(
      ([label, value]) => `
        <article class="metric-card">
          <span>${label}</span>
          <strong>${value}</strong>
        </article>
      `,
    )
    .join("");
}

function renderCodeBox(element, value) {
  if (!element) {
    return;
  }
  element.textContent = JSON.stringify(value, null, 2);
  element.classList.remove("empty-state");
}

function renderInlineNotice(element, message, tone = "info") {
  if (!element) {
    return;
  }
  if (!message) {
    element.textContent = "";
    element.classList.add("is-hidden");
    element.dataset.tone = "info";
    return;
  }

  element.textContent = message;
  element.dataset.tone = tone;
  element.classList.remove("is-hidden");
}

function formatDecimal(value, digits = 2) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return value;
  }
  return numeric.toFixed(digits);
}

function formatSignedDecimal(value, digits = 2, suffix = "") {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "n/a";
  }
  const prefix = numeric > 0 ? "+" : "";
  return `${prefix}${numeric.toFixed(digits)}${suffix}`;
}

function getLegacyPortfolioWatchlist() {
  try {
    const parsed = JSON.parse(localStorage.getItem("prognose.portfolioWatchlist") || "[]");
    if (!Array.isArray(parsed)) {
      return [];
    }
    return [...new Set(parsed.map((item) => String(item || "").trim().toUpperCase()).filter(Boolean))].slice(0, 12);
  } catch {
    return [];
  }
}

function clearLegacyPortfolioWatchlist() {
  localStorage.removeItem("prognose.portfolioWatchlist");
}

function isWatchedSymbol(symbol) {
  return state.portfolioMarket.watchlist.includes(String(symbol || "").trim().toUpperCase());
}

async function persistPortfolioWatchlistSymbol(symbol, shouldWatch) {
  const normalized = String(symbol || "").trim().toUpperCase();
  if (!normalized) {
    return false;
  }

  if (shouldWatch) {
    await api("/portfolio/watchlist", {
      method: "POST",
      body: JSON.stringify({ symbol: normalized }),
    });
    if (!isWatchedSymbol(normalized)) {
      state.portfolioMarket.watchlist = [...state.portfolioMarket.watchlist, normalized].slice(0, 12);
    }
  } else {
    await api(`/portfolio/watchlist/${encodeURIComponent(normalized)}`, {
      method: "DELETE",
    });
    state.portfolioMarket.watchlist = state.portfolioMarket.watchlist.filter((item) => item !== normalized);
  }

  return isWatchedSymbol(normalized);
}

async function togglePortfolioWatchlist(symbol) {
  return persistPortfolioWatchlistSymbol(symbol, !isWatchedSymbol(symbol));
}

async function loadPortfolioWatchlist({ log = true } = {}) {
  const payload = await api("/portfolio/watchlist");
  state.portfolioMarket.watchlist = (payload.items || []).map((item) => String(item.symbol || "").trim().toUpperCase()).filter(Boolean);
  if (log) {
    logResult("GET /portfolio/watchlist", payload);
  }
  return state.portfolioMarket.watchlist;
}

async function migrateLegacyPortfolioWatchlist() {
  const legacySymbols = getLegacyPortfolioWatchlist();
  if (!legacySymbols.length) {
    return;
  }

  for (const symbol of legacySymbols) {
    if (isWatchedSymbol(symbol)) {
      continue;
    }
    try {
      await persistPortfolioWatchlistSymbol(symbol, true);
    } catch {
      continue;
    }
  }
  clearLegacyPortfolioWatchlist();
}

function syncPortfolioTradeForm() {
  const tradeForm = byId("trade-form");
  if (!tradeForm) {
    return;
  }

  const symbolInput = tradeForm.querySelector("input[name='symbol']");
  if (symbolInput) {
    symbolInput.value = state.portfolioMarket.selectedAsset?.symbol || "";
  }
}

function renderPortfolioSearchResults(items = state.portfolioMarket.searchResults) {
  if (!els.portfolioSearchResults) {
    return;
  }

  if (!state.portfolioMarket.searchQuery.trim()) {
    els.portfolioSearchResults.textContent = "Начни вводить тикер или название компании.";
    els.portfolioSearchResults.classList.add("empty-state");
    return;
  }

  if (!items.length) {
    els.portfolioSearchResults.textContent = "По этому запросу поддерживаемые активы не найдены.";
    els.portfolioSearchResults.classList.add("empty-state");
    return;
  }

  els.portfolioSearchResults.classList.remove("empty-state");
  els.portfolioSearchResults.innerHTML = items
    .map(
      (asset) => `
        <article class="data-card market-search-card">
          <div class="position-card-head">
            <h4>${asset.symbol}</h4>
            <span class="position-badge is-${asset.asset_type}">${asset.asset_type}</span>
          </div>
          <p>${asset.name}</p>
          <p>${asset.exchange}${asset.sector ? ` · ${asset.sector}` : ""}</p>
          <div class="inline-actions">
            <button type="button" class="ghost-button portfolio-select-button" data-symbol="${asset.symbol}">Открыть</button>
            <button type="button" class="ghost-button portfolio-watch-toggle" data-symbol="${asset.symbol}">${isWatchedSymbol(asset.symbol) ? "Убрать из watchlist" : "В watchlist"}</button>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderMarketFocusCard(asset = state.portfolioMarket.selectedAsset) {
  if (!els.marketFocus) {
    return;
  }

  syncPortfolioTradeForm();
  if (!asset) {
    els.marketFocus.textContent = "Выбери актив из поиска или watchlist, чтобы увидеть цену и детали.";
    els.marketFocus.classList.add("empty-state");
    return;
  }

  const changeClass = Number(asset.change || 0) >= 0 ? "is-positive" : "is-negative";
  els.marketFocus.classList.remove("empty-state");
  els.marketFocus.innerHTML = `
    <div class="market-focus-head">
      <div>
        <p class="eyebrow">${asset.asset_type} · ${asset.exchange}</p>
        <h3>${asset.symbol}</h3>
        <p>${asset.name}</p>
      </div>
      <div class="market-focus-actions">
        <button type="button" class="ghost-button portfolio-refresh-quote" data-symbol="${asset.symbol}">Обновить цену</button>
        <button type="button" class="ghost-button portfolio-watch-toggle" data-symbol="${asset.symbol}">${isWatchedSymbol(asset.symbol) ? "Убрать из watchlist" : "В watchlist"}</button>
      </div>
    </div>
    <div class="market-focus-price-row">
      <strong>${formatDecimal(asset.current_price, 2)} ${asset.currency || "USD"}</strong>
      <span class="market-move ${changeClass}">${formatSignedDecimal(asset.change, 2)} · ${formatSignedDecimal(asset.change_percent, 2, "%")}</span>
    </div>
    <div class="market-focus-metrics">
      <article><span>Prev close</span><strong>${asset.previous_close ? formatDecimal(asset.previous_close, 2) : "n/a"}</strong></article>
      <article><span>Day range</span><strong>${asset.day_low ? formatDecimal(asset.day_low, 2) : "n/a"} - ${asset.day_high ? formatDecimal(asset.day_high, 2) : "n/a"}</strong></article>
      <article><span>Volume</span><strong>${asset.volume || "n/a"}</strong></article>
      <article><span>Source</span><strong>${asset.source || "Yahoo"}</strong></article>
    </div>
  `;
}

function renderPortfolioHoldings(items) {
  if (!els.portfolioHoldings) {
    return;
  }

  if (!items.length) {
    els.portfolioHoldings.textContent = "Открытых позиций пока нет.";
    els.portfolioHoldings.classList.add("empty-state");
    return;
  }

  els.portfolioHoldings.classList.remove("empty-state");
  els.portfolioHoldings.innerHTML = items
    .map(
      (holding) => `
        <article class="data-card holding-card">
          <div class="position-card-head">
            <h4>${holding.symbol}</h4>
            <span class="position-badge is-${holding.asset_type}">${holding.asset_type}</span>
          </div>
          <p>${holding.name}</p>
          <p>Qty ${formatDecimal(holding.quantity, 4)} · avg ${formatDecimal(holding.average_cost, 2)}</p>
          <p>Value ${formatDecimal(holding.market_value, 2)} · cost ${formatDecimal(holding.cost_basis, 2)}</p>
          <p class="market-move ${Number(holding.unrealized_pnl) >= 0 ? "is-positive" : "is-negative"}">Unrealized ${formatSignedDecimal(holding.unrealized_pnl, 2)}</p>
        </article>
      `,
    )
    .join("");
}

function renderPortfolioTrades(items) {
  if (!els.portfolioTrades) {
    return;
  }

  if (!items.length) {
    els.portfolioTrades.textContent = "Сделок пока нет.";
    els.portfolioTrades.classList.add("empty-state");
    return;
  }

  els.portfolioTrades.classList.remove("empty-state");
  els.portfolioTrades.innerHTML = items
    .map(
      (trade) => `
        <article class="table-row">
          <h4>${trade.symbol} · ${trade.side}</h4>
          <p>${formatDecimal(trade.quantity, 4)} units at ${formatDecimal(trade.price, 2)}</p>
          <p>Gross ${formatDecimal(trade.gross_amount, 2)} · ${new Date(trade.created_at).toLocaleString()}</p>
        </article>
      `,
    )
    .join("");
}

async function searchPortfolioAssets(query, { log = true } = {}) {
  const normalizedQuery = String(query || "").trim();
  state.portfolioMarket.searchQuery = normalizedQuery;

  if (normalizedQuery.length < 2) {
    state.portfolioMarket.searchResults = [];
    renderPortfolioSearchResults();
    return [];
  }

  const payload = await api(`/assets/search?q=${encodeURIComponent(normalizedQuery)}&limit=8`, { skipAuth: true });
  state.portfolioMarket.searchResults = payload.items || [];
  renderPortfolioSearchResults();
  if (log) {
    logResult(`GET /assets/search?q=${normalizedQuery}`, payload);
  }
  return payload.items || [];
}

function updatePortfolioTradeEstimate() {
  if (!els.marketFocusNotice || !state.portfolioMarket.selectedAsset) {
    return;
  }

  const quantityInput = byId("trade-quantity");
  const quantity = Number(quantityInput?.value || 0);
  if (!Number.isFinite(quantity) || quantity <= 0) {
    renderInlineNotice(
      els.marketFocusNotice,
      `Текущая цена ${formatDecimal(state.portfolioMarket.selectedAsset.current_price, 2)} ${state.portfolioMarket.selectedAsset.currency || "USD"}. Укажи количество, чтобы увидеть оценку сделки.`,
      "info",
    );
    return;
  }

  const estimatedGross = Number(state.portfolioMarket.selectedAsset.current_price || 0) * quantity;
  renderInlineNotice(els.marketFocusNotice, `Оценка сделки: ${formatDecimal(estimatedGross, 2)} ${state.portfolioMarket.selectedAsset.currency || "USD"}.`, "info");
}

async function loadMarketAssetQuote(symbol, { log = true } = {}) {
  const payload = await api(`/assets/${encodeURIComponent(symbol)}/quote`, { skipAuth: true });
  state.portfolioMarket.selectedAsset = payload.asset || null;
  renderMarketFocusCard();
  updatePortfolioTradeEstimate();
  renderPortfolioSearchResults();
  if (log) {
    logResult(`GET /assets/${symbol}/quote`, payload);
  }
  return payload.asset;
}

function getQuotePreview(wrapper) {
  return wrapper?.querySelector("[data-role='quote-preview']");
}

function renderQuotePreview(wrapper, message, tone = "idle") {
  const element = getQuotePreview(wrapper);
  if (!element) {
    return;
  }

  element.textContent = message;
  element.dataset.tone = tone;
}

function updateTradeControls(wrapper) {
  if (!wrapper) {
    return;
  }

  const confirmButton = wrapper.querySelector(".confirm-predict-button");
  const stakeInput = wrapper.querySelector(".stake-input");
  const selectedOutcomeId = wrapper.dataset.selectedOutcomeId;
  const stakeValue = Number(stakeInput?.value || 0);
  const isValidStake = Number.isFinite(stakeValue) && stakeValue > 0;

  wrapper.querySelectorAll(".predict-button").forEach((button) => {
    button.classList.toggle("is-selected", button.dataset.outcomeId === selectedOutcomeId);
  });

  if (confirmButton) {
    confirmButton.disabled = confirmButton.dataset.closed === "true" || !selectedOutcomeId || !isValidStake;
  }
}

async function requestEventQuote(wrapper) {
  if (!wrapper || wrapper.dataset.closed === "true") {
    return;
  }

  const eventId = wrapper.dataset.eventId;
  const stakeInput = wrapper.querySelector(".stake-input");
  const selectedOutcomeId = wrapper.dataset.selectedOutcomeId;
  const stake = Number(stakeInput?.value || 0);
  const selectedButton = wrapper.querySelector(`.predict-button[data-outcome-id='${selectedOutcomeId}']`);
  const outcomeLabel = selectedButton?.dataset.outcomeLabel || "выбранный исход";

  if (!selectedOutcomeId || !Number.isFinite(stake) || stake <= 0) {
    renderQuotePreview(wrapper, "Введи сумму и выбери исход, чтобы увидеть, сколько долей ты купишь по текущей LMSR-цене.");
    updateTradeControls(wrapper);
    return;
  }

  const requestId = (eventQuoteRequestSeq.get(eventId) || 0) + 1;
  eventQuoteRequestSeq.set(eventId, requestId);
  renderQuotePreview(wrapper, "Считаю котировку...", "loading");

  try {
    const result = await api(`/events/${eventId}/quote`, {
      method: "POST",
      body: JSON.stringify({ outcome_id: Number(selectedOutcomeId), stake_amount: stakeInput.value }),
    });

    if (eventQuoteRequestSeq.get(eventId) !== requestId) {
      return;
    }

    const quote = result.quote || {};
    const postTradeOutcome = result.event?.outcomes?.find((outcome) => String(outcome.id) === String(selectedOutcomeId));
    const postTradeProbability = postTradeOutcome ? formatDecimal(postTradeOutcome.probability_pct, 1) : null;
    const averagePrice = quote.average_price ? formatDecimal(quote.average_price, 4) : null;
    const shareQuantity = quote.share_quantity ? formatDecimal(quote.share_quantity, 3) : null;

    renderQuotePreview(
      wrapper,
      `Покупка ${outcomeLabel}: ≈ ${shareQuantity} долей по средней цене ${averagePrice}. После сделки игровая вероятность будет около ${postTradeProbability}%.`,
      "success",
    );
  } catch (error) {
    if (eventQuoteRequestSeq.get(eventId) !== requestId) {
      return;
    }
    renderQuotePreview(wrapper, error.message, "error");
  } finally {
    updateTradeControls(wrapper);
  }
}

function scheduleEventQuote(wrapper) {
  if (!wrapper) {
    return;
  }

  const eventId = wrapper.dataset.eventId;
  const previousTimer = eventQuoteTimers.get(eventId);
  if (previousTimer) {
    clearTimeout(previousTimer);
  }

  const timer = window.setTimeout(() => {
    eventQuoteTimers.delete(eventId);
    requestEventQuote(wrapper).catch(() => undefined);
  }, 220);

  eventQuoteTimers.set(eventId, timer);
}

function datetimeLocalToIso(value) {
  return value ? new Date(value).toISOString() : null;
}

async function loadMe() {
  const payload = await api("/me");
  toggleAdminLinks(Boolean(payload.is_admin));
  renderMetricCards(els.accountMetrics, [
    ["Handle", payload.handle],
    ["Баланс", payload.wallet.current_balance],
    ["Подписка", payload.subscription.plan.code],
    ["Email verified", payload.email_verified ? "yes" : "no"],
    ["Login fails", payload.account_flags.failed_login_attempts],
    ["Suspicious", payload.account_flags.suspicious_activity ? "yes" : "no"],
  ]);
  state.recentPredictions = payload.recent_predictions || [];
  renderMyPositions();
  renderMyCreatedEvents(payload.recent_created_events || []);
  renderCodeBox(els.accountJson, payload);
  logResult("GET /me", payload);
  return payload;
}

function renderMyCreatedEvents(items) {
  if (!els.myCreatedEventsList) {
    return;
  }

  if (!items.length) {
    els.myCreatedEventsList.textContent = "Ты еще не создавал события.";
    els.myCreatedEventsList.classList.add("empty-state");
    return;
  }

  els.myCreatedEventsList.classList.remove("empty-state");
  els.myCreatedEventsList.innerHTML = items
    .map(
      (event) => `
        <article class="data-card position-card">
          <div class="position-card-head">
            <h4>${event.title}</h4>
            <span class="position-badge is-${event.status}">${event.status}</span>
          </div>
          <p>${event.category} · закрытие ${new Date(event.closes_at).toLocaleString()}</p>
          <p>${event.status === "pending_review" ? "Ждет одобрения админом и пока не видно другим пользователям." : "Событие уже активно для участников или завершено."}</p>
          <p>${event.moderation_notes ? `Заметка модерации: ${event.moderation_notes}` : "Без заметок модерации"}</p>
        </article>
      `,
    )
    .join("");
}

function getFilteredPositions() {
  const query = state.positionFilters.query.trim().toLowerCase();
  const status = state.positionFilters.status;

  return state.recentPredictions.filter((position) => {
    const matchesStatus = status === "all" || position.status === status;
    if (!matchesStatus) {
      return false;
    }

    if (!query) {
      return true;
    }

    const haystack = [position.event_title, position.outcome_label, position.status, position.event_status]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(query);
  });
}

function renderMyPositions() {
  if (!els.myPositionsList) {
    return;
  }

  const items = getFilteredPositions();

  if (!state.recentPredictions.length) {
    els.myPositionsList.textContent = "У тебя пока нет открытых или завершенных позиций.";
    els.myPositionsList.classList.add("empty-state");
    return;
  }

  if (!items.length) {
    els.myPositionsList.textContent = "По текущему фильтру позиции не найдены.";
    els.myPositionsList.classList.add("empty-state");
    return;
  }

  els.myPositionsList.classList.remove("empty-state");
  els.myPositionsList.innerHTML = items
    .map(
      (position) => `
        <article class="data-card position-card">
          <div class="position-card-head">
            <h4>${position.event_title}</h4>
            <span class="position-badge is-${position.status}">${position.status}</span>
          </div>
          <p>${position.outcome_label} · stake ${formatDecimal(position.stake_amount, 2)} · shares ${formatDecimal(position.share_quantity, 3)}</p>
          <p>avg price ${formatDecimal(position.average_price, 4)} · event ${position.event_status}</p>
          <p>${position.payout_amount && Number(position.payout_amount) > 0 ? `payout ${formatDecimal(position.payout_amount, 2)}` : "Выплата еще не зафиксирована"}</p>
          <p>${new Date(position.created_at).toLocaleString()}</p>
        </article>
      `,
    )
    .join("");
}

function renderEvents(items) {
  if (!els.eventsList) {
    return;
  }
  if (!items.length) {
    els.eventsList.textContent = "Событий пока нет.";
    els.eventsList.classList.add("empty-state");
    return;
  }

  els.eventsList.classList.remove("empty-state");
  els.eventsList.innerHTML = items
    .map(
      (event) => `
        ${(() => {
          const isClosed = event.status !== "open" || new Date(event.closes_at) <= new Date();
          const stateLabel = isClosed ? "Ставки закрыты" : "Можно поставить прогноз";
          const marketSummary = event.market_state?.outcomes?.length
            ? `<div class="market-summary">${event.market_state.outcomes
                .map((outcome) => `<span>${outcome.label}: ${Number(outcome.probability_pct).toFixed(1)}%</span>`)
                .join("")}</div>`
            : "";
          return `
        <article class="data-card">
          <h4>${event.title}</h4>
          <p>${event.category} · ${event.status}</p>
          <p>${event.description || "Без описания"}</p>
          <p>Закрытие: ${new Date(event.closes_at).toLocaleString()}</p>
          <p class="event-state ${isClosed ? "is-closed" : "is-open"}">${stateLabel}</p>
          ${marketSummary}
          <div class="mini-form trade-form" data-event-id="${event.id}" data-closed="${isClosed ? "true" : "false"}" data-selected-outcome-id="">
            <input type="number" step="0.01" min="1" placeholder="Сумма прогноза" class="stake-input" ${isClosed ? "disabled" : ""}>
            <div class="outcomes">
              ${event.outcomes
                .map(
                  (outcome) => `<button type="button" class="predict-button" data-event-id="${event.id}" data-outcome-id="${outcome.id}" data-outcome-label="${outcome.label}" ${isClosed ? "disabled" : ""}>${outcome.label} · ${Number(outcome.probability_pct).toFixed(1)}%</button>`,
                )
                .join("")}
            </div>
            <div class="quote-preview" data-role="quote-preview" data-tone="idle">Введи сумму и выбери исход, чтобы увидеть, сколько долей ты купишь по текущей LMSR-цене.</div>
            <button type="button" class="confirm-predict-button" data-closed="${isClosed ? "true" : "false"}" disabled>Подтвердить покупку позиции</button>
          </div>
        </article>
      `;
        })()}
      `,
    )
    .join("");
}

async function loadEvents() {
  const payload = await api("/events", { skipAuth: true });
  renderEvents(payload.items);
  logResult("GET /events", payload);
}

function renderAssets(items) {
  if (!els.assetsList) {
    return;
  }
  if (!items.length) {
    els.assetsList.textContent = "Отметь активы из поиска, чтобы собрать свой market dashboard.";
    els.assetsList.classList.add("empty-state");
    return;
  }
  els.assetsList.classList.remove("empty-state");
  els.assetsList.innerHTML = items
    .map(
      (asset) => `
        <article class="data-card watchlist-card">
          <div class="position-card-head">
            <h4>${asset.symbol}</h4>
            <span class="position-badge is-${asset.asset_type}">${asset.asset_type}</span>
          </div>
          <p>${asset.name}</p>
          <p>${asset.exchange || "n/a"}</p>
          <p><strong>${formatDecimal(asset.current_price, 2)} ${asset.currency || "USD"}</strong></p>
          <p class="market-move ${Number(asset.change || 0) >= 0 ? "is-positive" : "is-negative"}">${formatSignedDecimal(asset.change, 2)} · ${formatSignedDecimal(asset.change_percent, 2, "%")}</p>
          <div class="inline-actions">
            <button type="button" class="ghost-button portfolio-select-button" data-symbol="${asset.symbol}">Открыть</button>
            <button type="button" class="ghost-button portfolio-watch-toggle" data-symbol="${asset.symbol}">Убрать</button>
          </div>
        </article>
      `,
    )
    .join("");
}

async function loadAssets({ log = true } = {}) {
  const symbols = state.portfolioMarket.watchlist;
  if (!symbols.length) {
    renderAssets([]);
    return [];
  }

  const payload = await api(`/assets/quotes?symbols=${encodeURIComponent(symbols.join(","))}`, { skipAuth: true });
  const items = payload.items || [];
  renderAssets(items);
  const selectedSymbol = state.portfolioMarket.selectedAsset?.symbol;
  if (selectedSymbol) {
    const updatedSelected = items.find((item) => item.symbol === selectedSymbol);
    if (updatedSelected) {
      state.portfolioMarket.selectedAsset = {
        ...state.portfolioMarket.selectedAsset,
        ...updatedSelected,
      };
      renderMarketFocusCard();
      updatePortfolioTradeEstimate();
    }
  }
  if (log) {
    logResult("GET /assets/quotes", payload);
  }
  return items;
}

async function loadPortfolio() {
  const payload = await api("/portfolio/me");
  renderMetricCards(els.portfolioMetrics, [
    ["Market value", payload.summary.market_value],
    ["Return %", payload.summary.return_pct],
    ["Realized PnL", payload.summary.realized_pnl],
    ["Unrealized PnL", payload.summary.unrealized_pnl],
    ["Cash", payload.summary.available_cash],
    ["Positions", payload.summary.open_positions_count],
  ]);
  renderPortfolioHoldings(payload.holdings || []);
  renderPortfolioTrades(payload.recent_trades || []);
  logResult("GET /portfolio/me", payload);
  return payload;
}

async function refreshPortfolioMarketData() {
  const requests = [];
  if (state.portfolioMarket.selectedAsset?.symbol) {
    requests.push(loadMarketAssetQuote(state.portfolioMarket.selectedAsset.symbol, { log: false }).catch(() => undefined));
  }
  requests.push(loadAssets({ log: false }).catch(() => undefined));
  await Promise.all(requests);
}

function schedulePortfolioMarketRefresh() {
  if (portfolioMarketRefreshTimer) {
    clearInterval(portfolioMarketRefreshTimer);
  }
  portfolioMarketRefreshTimer = window.setInterval(() => {
    refreshPortfolioMarketData().catch(() => undefined);
  }, 7000);
}

async function syncPortfolioWatchlistAndAssets() {
  await loadPortfolioWatchlist({ log: false });
  await migrateLegacyPortfolioWatchlist();
  renderPortfolioSearchResults();
  await loadAssets({ log: false });
}

function renderBoard(element, items) {
  if (!element) {
    return;
  }
  if (!items.length) {
    element.textContent = "Рейтинг пока пуст.";
    element.classList.add("empty-state");
    return;
  }
  element.classList.remove("empty-state");
  element.innerHTML = items
    .map(
      (row) => `
        <article class="table-row">
          <h4>#${row.rank} · ${row.handle}</h4>
          <p>Score: ${row.score}</p>
          <p>${Object.entries(row.metrics)
            .slice(0, 3)
            .map(([key, value]) => `${key}: ${value}`)
            .join(" · ")}</p>
        </article>
      `,
    )
    .join("");
}

async function loadBoard(type) {
  const payload = await api(`/leaderboards/${type}?refresh=true`, { skipAuth: true });
  renderBoard(type === "predictions" ? els.predictionBoard : els.portfolioBoard, payload.items);
  logResult(`GET /leaderboards/${type}`, payload);
}

function renderFeed(items) {
  if (!els.feedList) {
    return;
  }
  if (!items.length) {
    els.feedList.textContent = "Лента пока пустая.";
    els.feedList.classList.add("empty-state");
    return;
  }
  els.feedList.classList.remove("empty-state");
  els.feedList.innerHTML = items
    .map(
      (item) => `
        <article class="data-card">
          <h4>${item.handle}</h4>
          <p>${item.outcome} · ${item.stake_amount} игровых евро</p>
          <p>${new Date(item.created_at).toLocaleString()}</p>
        </article>
      `,
    )
    .join("");
}

async function loadFeed() {
  const payload = await api("/social/feed");
  renderFeed(payload.items);
  logResult("GET /social/feed", payload);
}

function renderPlans(items) {
  if (!els.plansGrid) {
    return;
  }
  if (!items.length) {
    els.plansGrid.textContent = "Тарифы пока недоступны.";
    els.plansGrid.classList.add("empty-state");
    return;
  }

  els.plansGrid.classList.remove("empty-state");
  els.plansGrid.innerHTML = items
    .map(
      (plan) => `
        <article class="plan-card ${plan.code !== "free" ? "featured" : ""}">
          <p class="eyebrow">${plan.code}</p>
          <h4>${plan.name}</h4>
          <p>${plan.monthly_price} ${plan.currency}/month</p>
          <p>max_follows: ${plan.entitlements.max_follows}</p>
          <p>advanced_analytics: ${plan.entitlements.advanced_analytics ? "yes" : "no"}</p>
          ${plan.code === "free" ? "" : `<button class="checkout-button" data-plan="${plan.code}">Mock checkout</button>`}
        </article>
      `,
    )
    .join("");
}

async function loadPlans() {
  const payload = await api("/billing/plans", { skipAuth: true });
  renderPlans(payload.items);
  logResult("GET /billing/plans", payload);
}

async function loadBillingMe() {
  const payload = await api("/billing/me");
  const subscription = payload.subscription;
  renderMetricCards(els.billingMetrics, [
    ["Plan", subscription.plan.code],
    ["Status", subscription.status],
    ["Since", subscription.started_at ? new Date(subscription.started_at).toLocaleDateString() : "n/a"],
    ["Max follows", subscription.entitlements.max_follows],
  ]);
  renderCodeBox(els.billingJson, payload);
  logResult("GET /billing/me", payload);
}

async function submitJsonForm(event, path, transform, options = {}) {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const payload = transform(formData);
  const result = await api(path, {
    method: options.method || "POST",
    body: JSON.stringify(payload),
    skipAuth: options.skipAuth || false,
  });
  logResult(`${options.method || "POST"} ${path}`, result);
  return result;
}

function renderAdminUsers(items) {
  if (!els.adminUsersList) {
    return;
  }
  if (!items.length) {
    els.adminUsersList.textContent = "Пользователи еще не загружены.";
    els.adminUsersList.classList.add("empty-state");
    return;
  }

  els.adminUsersList.classList.remove("empty-state");
  els.adminUsersList.innerHTML = items
    .map(
      (user) => `
        <article class="table-row">
          <h4>#${user.id} · ${user.handle}</h4>
          <p>${user.email}</p>
          <p>admin: ${user.is_admin ? "yes" : "no"} · verified: ${user.email_verified ? "yes" : "no"}</p>
          <p>fails: ${user.failed_login_attempts} · suspicious: ${user.suspicious_activity ? "yes" : "no"}</p>
          <p>balance: ${user.wallet_balance ?? "n/a"}</p>
          <form class="mini-form admin-credit-form" data-user-id="${user.id}" data-user-handle="${user.handle}">
            <input name="amount" type="number" step="0.01" min="0.01" placeholder="Сумма пополнения" required>
            <input name="note" type="text" maxlength="120" placeholder="Причина, например support credit">
            <button type="submit">Пополнить баланс</button>
          </form>
        </article>
      `,
    )
    .join("");
}

function renderAdminEvents(items) {
  if (!els.adminEventsList) {
    return;
  }
  if (!items.length) {
    els.adminEventsList.textContent = "События еще не загружены.";
    els.adminEventsList.classList.add("empty-state");
    return;
  }

  els.adminEventsList.classList.remove("empty-state");
  els.adminEventsList.innerHTML = items
    .map(
      (event) => `
        <article class="data-card">
          <h4>#${event.id} · ${event.title}</h4>
          <p>${event.category} · ${event.status}</p>
          <p>Создатель: ${event.creator_id}</p>
          <div class="mini-form" data-admin-event-id="${event.id}">
            <select class="resolve-outcome-id">
              <option value="">Выбери исход для резолва</option>
              ${event.outcomes
                .map((outcome) => `<option value="${outcome.id}">${outcome.label}</option>`)
                .join("")}
            </select>
            <button type="button" class="resolve-event-button" data-event-id="${event.id}">Резолвить</button>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderPendingAdminEvents(items) {
  if (!els.adminPendingEventsList) {
    return;
  }
  if (!items.length) {
    els.adminPendingEventsList.textContent = "Очередь модерации пуста.";
    els.adminPendingEventsList.classList.add("empty-state");
    return;
  }

  els.adminPendingEventsList.classList.remove("empty-state");
  els.adminPendingEventsList.innerHTML = items
    .map(
      (event) => `
        <article class="data-card">
          <h4>#${event.id} · ${event.title}</h4>
          <p>${event.category} · creator ${event.creator_id}</p>
          <p>${event.description || "Без описания"}</p>
          <p>Source: ${event.source_of_truth}</p>
          <p>Outcomes: ${event.outcomes.map((outcome) => outcome.label).join(", ")}</p>
          <textarea class="moderation-notes" placeholder="Причина решения"></textarea>
          <div class="inline-actions">
            <button type="button" class="moderate-event-button" data-event-id="${event.id}" data-decision="approve">Одобрить</button>
            <button type="button" class="ghost-button moderate-event-button" data-event-id="${event.id}" data-decision="reject">Отклонить</button>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderAiGenerationResults(items) {
  if (!els.adminAiResults) {
    return;
  }
  if (!items.length) {
    els.adminAiResults.textContent = "AI generation не вернула кандидатов. Попробуй другие темы или источники.";
    els.adminAiResults.classList.add("empty-state");
    return;
  }

  els.adminAiResults.classList.remove("empty-state");
  els.adminAiResults.innerHTML = items
    .map(
      (item) => `
        <article class="data-card ai-result-card">
          <div class="position-card-head">
            <h4>${item.title}</h4>
            <span class="position-badge is-${item.publication_status}">${item.publication_status}</span>
          </div>
          <p>${item.category} · confidence ${formatDecimal(item.confidence, 2)}</p>
          <p>${item.selection_reason || item.rationale || "Без пояснения модели"}</p>
          <p>Resolve source: ${item.source_of_truth}</p>
          <p>Window: ${new Date(item.closes_at).toLocaleString()} -> ${new Date(item.resolves_at).toLocaleString()}</p>
          <p>AI stance: ${item.recommended_outcome} · stake ${formatDecimal(item.recommended_stake, 2)}</p>
          <p>${item.event_id ? `Created as event #${item.event_id} with status ${item.event_status || item.publication_status}` : "Пока не создано"}</p>
          <p>${item.seed_prediction?.status === "created" ? `Bot seeded ${item.seed_prediction.outcome_label} with ${item.seed_prediction.stake_amount}` : (item.seed_prediction?.reason || "Без AI seed-позиции")}</p>
        </article>
      `,
    )
    .join("");
}

function normalizeAiSourceUrls(rawValue) {
  return String(rawValue || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 5);
}

function normalizeAiSourceNotes(rawValue) {
  const compact = String(rawValue || "").replace(/\r/g, "").trim();
  if (!compact) {
    return [];
  }

  const noteLimit = 6000;
  const normalized = compact.length > noteLimit ? compact.slice(0, noteLimit) : compact;
  return normalized
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 12);
}

async function loadAdminDashboard() {
  const payload = await api("/admin/dashboard");
  renderMetricCards(els.adminMetrics, [
    ["Users", payload.users_total],
    ["Admins", payload.admins_total],
    ["Pending", payload.pending_events],
    ["Open events", payload.open_events],
    ["Resolved", payload.resolved_events],
    ["Suspicious", payload.suspicious_users],
    ["Assets", payload.assets_total],
  ]);
  logResult("GET /admin/dashboard", payload);
}

async function loadAdminUsers() {
  const payload = await api("/admin/users");
  renderAdminUsers(payload.items);
  logResult("GET /admin/users", payload);
}

async function loadAdminEvents() {
  const payload = await api("/admin/events");
  renderAdminEvents(payload.items);
  logResult("GET /admin/events", payload);
}

async function loadAdminPendingEvents() {
  const payload = await api("/admin/events/pending");
  renderPendingAdminEvents(payload.items);
  logResult("GET /admin/events/pending", payload);
}

function registerCommonHandlers() {
  setApiBase(state.apiBase);
  if (els.frontendOrigin) {
    els.frontendOrigin.textContent = window.location.origin;
  }

  bind("save-api-base", "click", () => setApiBase((els.apiBase?.value || "").trim()));
  bind("clear-log", "click", () => {
    if (els.activityLog) {
      els.activityLog.textContent = "Лог пока пуст.";
    }
  });

  bind("refresh-access", "click", async () => {
    if (!state.refreshToken) {
      alert("Сначала войди в аккаунт.");
      return;
    }
    try {
      const response = await fetch(`${state.apiBase}/auth/refresh`, {
        method: "POST",
        headers: { Authorization: `Bearer ${state.refreshToken}` },
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
      saveTokens(result.access_token, null);
      logResult("POST /auth/refresh", result);
    } catch (error) {
      alert(error.message);
    }
  });

  bind("logout-button", "click", () => {
    clearSession();
    window.location.href = "/login";
  });

  bind("load-me", "click", () => loadMe().catch((error) => alert(error.message)));
  bind("load-events", "click", () => loadEvents().catch((error) => alert(error.message)));
  bind("load-assets", "click", () => syncPortfolioWatchlistAndAssets().catch((error) => renderInlineNotice(els.marketFocusNotice, error.message, "error")));
  bind("load-portfolio", "click", () => loadPortfolio().catch((error) => alert(error.message)));
  bind("load-feed", "click", () => loadFeed().catch((error) => alert(error.message)));
  bind("load-plans", "click", () => loadPlans().catch((error) => alert(error.message)));
  bind("load-billing-me", "click", () => loadBillingMe().catch((error) => alert(error.message)));
  bind("load-admin-dashboard", "click", () => loadAdminDashboard().catch((error) => alert(error.message)));
  bind("load-admin-users", "click", () => loadAdminUsers().catch((error) => alert(error.message)));
  bind("load-admin-events", "click", () => loadAdminEvents().catch((error) => alert(error.message)));
  bind("load-admin-pending-events", "click", () => loadAdminPendingEvents().catch((error) => alert(error.message)));
  bind("portfolio-search-form", "submit", async (event) => {
    event.preventDefault();
    try {
      await searchPortfolioAssets(els.portfolioSearchQuery?.value || "");
    } catch (error) {
      renderInlineNotice(els.marketFocusNotice, error.message, "error");
    }
  });
  bind("portfolio-search-query", "input", (event) => {
    const query = event.target.value || "";
    window.clearTimeout(portfolioSearchDebounceTimer);
    portfolioSearchDebounceTimer = window.setTimeout(() => {
      searchPortfolioAssets(query, { log: false }).catch((error) => renderInlineNotice(els.marketFocusNotice, error.message, "error"));
    }, 220);
  });
  bind("trade-quantity", "input", () => updatePortfolioTradeEstimate());
  bind("positions-search", "input", (event) => {
    state.positionFilters.query = event.target.value || "";
    renderMyPositions();
  });
  bind("positions-status-filter", "change", (event) => {
    state.positionFilters.status = event.target.value || "all";
    renderMyPositions();
  });

  document.querySelectorAll(".refresh-board").forEach((button) => {
    button.addEventListener("click", () => loadBoard(button.dataset.board).catch((error) => alert(error.message)));
  });

  bind("event-form", "submit", async (event) => {
    try {
      renderInlineNotice(els.eventsFeedback, "");
      const result = await submitJsonForm(event, "/events", (formData) => ({
        title: formData.get("title"),
        category: formData.get("category"),
        source_of_truth: formData.get("source_of_truth"),
        description: formData.get("description"),
        closes_at: datetimeLocalToIso(formData.get("closes_at")),
        resolves_at: datetimeLocalToIso(formData.get("resolves_at")),
        outcomes: String(formData.get("outcomes")).split(",").map((item) => item.trim()).filter(Boolean),
      }));
      if (result.event?.status === "pending_review") {
        renderInlineNotice(els.eventsFeedback, "Событие создано и отправлено на модерацию администратору.", "info");
      } else {
        renderInlineNotice(els.eventsFeedback, "Событие создано и уже открыто для прогнозов.", "success");
      }
      await loadEvents();
    } catch (error) {
      renderInlineNotice(els.eventsFeedback, error.message, "error");
    }
  });

  bind("trade-form", "submit", async (event) => {
    try {
      if (!state.portfolioMarket.selectedAsset?.symbol) {
        throw new Error("Сначала выбери актив из поиска или watchlist.");
      }

      renderInlineNotice(els.marketFocusNotice, "");
      await submitJsonForm(event, "/portfolio/trades", (formData) => ({
        symbol: formData.get("symbol"),
        side: formData.get("side"),
        quantity: formData.get("quantity"),
      }));
      renderInlineNotice(els.marketFocusNotice, `Сделка по ${state.portfolioMarket.selectedAsset.symbol} отправлена и записана в портфель.`, "success");
      await loadPortfolio();
      await Promise.all([
        loadAssets({ log: false }),
        loadMarketAssetQuote(state.portfolioMarket.selectedAsset.symbol, { log: false }),
        loadMe().catch(() => undefined),
      ]);
    } catch (error) {
      renderInlineNotice(els.marketFocusNotice, error.message, "error");
    }
  });

  bind("follow-form", "submit", async (event) => {
    event.preventDefault();
    const handle = new FormData(event.currentTarget).get("handle");
    try {
      const result = await api(`/users/${handle}/follow`, { method: "POST" });
      logResult(`POST /users/${handle}/follow`, result);
      await loadFeed().catch(() => undefined);
    } catch (error) {
      alert(error.message);
    }
  });

  bind("profile-form", "submit", async (event) => {
    event.preventDefault();
    const handle = new FormData(event.currentTarget).get("handle");
    try {
      const result = await api(`/users/${handle}`, { skipAuth: true });
      renderCodeBox(els.publicProfileJson, result.profile);
      logResult(`GET /users/${handle}`, result);
    } catch (error) {
      alert(error.message);
    }
  });

  bind("admin-asset-form", "submit", async (event) => {
    try {
      await submitJsonForm(event, "/admin/assets", (formData) => Object.fromEntries(formData));
      await loadAdminDashboard().catch(() => undefined);
    } catch (error) {
      alert(error.message);
    }
  });

  bind("admin-price-form", "submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    try {
      const assetId = formData.get("asset_id");
      const result = await api(`/admin/assets/${assetId}/price`, {
        method: "PATCH",
        body: JSON.stringify({ current_price: formData.get("current_price") }),
      });
      logResult(`PATCH /admin/assets/${assetId}/price`, result);
      await loadAdminDashboard().catch(() => undefined);
    } catch (error) {
      alert(error.message);
    }
  });

  bind("admin-ai-form", "submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const submitButton = form.querySelector("button[type='submit']");
    const formData = new FormData(form);
    const topics = String(formData.get("topics") || "").trim().slice(0, 500);
    const sourceUrls = normalizeAiSourceUrls(formData.get("source_urls"));
    const rawSourceNotes = String(formData.get("source_notes") || "");
    const sourceNotes = normalizeAiSourceNotes(rawSourceNotes);

    if (!topics && sourceUrls.length === 0 && sourceNotes.length === 0) {
      renderInlineNotice(els.adminAiFeedback, "Укажи тему и добавь хотя бы один URL или короткую заметку из браузера.", "error");
      return;
    }

    if (rawSourceNotes.length > 6000) {
      renderInlineNotice(els.adminAiFeedback, "Source notes слишком длинные. Оставь только несколько коротких абзацев или тезисов, максимум 6000 символов.", "error");
      return;
    }

    try {
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = "Генерация...";
      }
      renderInlineNotice(els.adminAiFeedback, "");
      const result = await api("/admin/ai/generate-events", {
        method: "POST",
        body: JSON.stringify({
          count: Number(formData.get("count") || 3),
          topics,
          source_urls: sourceUrls,
          source_notes: sourceNotes,
          publish_generated: formData.get("publish_generated") === "true",
          create_seed_predictions: formData.get("create_seed_predictions") === "true",
        }),
      });
      logResult("POST /admin/ai/generate-events", result);
      renderAiGenerationResults(result.items || []);
      const warningMessage = (result.warnings || []).length ? ` Предупреждения: ${(result.warnings || []).join(" | ")}` : "";
      renderInlineNotice(
        els.adminAiFeedback,
        `AI generation завершена. Модель ${result.used_model} вернула ${(result.items || []).length} кандидатов.${warningMessage}`,
        (result.warnings || []).length ? "info" : "success",
      );
      if (result.publish_generated) {
        await Promise.all([
          loadAdminDashboard().catch(() => undefined),
          loadAdminPendingEvents().catch(() => undefined),
          loadAdminEvents().catch(() => undefined),
          loadEvents().catch(() => undefined),
        ]);
      }
    } catch (error) {
      renderInlineNotice(els.adminAiFeedback, error.message, "error");
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = "Запустить AI generation";
      }
    }
  });

  if (els.eventsList) {
    els.eventsList.addEventListener("input", (event) => {
      const stakeInput = event.target.closest(".stake-input");
      if (!stakeInput) return;
      const wrapper = stakeInput.closest(".trade-form");
      updateTradeControls(wrapper);
      if (wrapper?.dataset.selectedOutcomeId) {
        scheduleEventQuote(wrapper);
      } else {
        renderQuotePreview(wrapper, "Сумма указана. Теперь выбери исход, чтобы получить котировку.");
      }
    });

    els.eventsList.addEventListener("click", async (event) => {
      const outcomeButton = event.target.closest(".predict-button");
      if (outcomeButton) {
        const wrapper = outcomeButton.closest(".trade-form");
        if (outcomeButton.disabled || wrapper?.dataset.closed === "true") {
          renderInlineNotice(els.eventsFeedback, "Ставка недоступна: рынок уже закрыт по времени или статусу.", "error");
          return;
        }

        wrapper.dataset.selectedOutcomeId = outcomeButton.dataset.outcomeId;
        updateTradeControls(wrapper);
        scheduleEventQuote(wrapper);
        return;
      }

      const confirmButton = event.target.closest(".confirm-predict-button");
      if (!confirmButton) return;

      const wrapper = confirmButton.closest(".trade-form");
      const eventId = wrapper?.dataset.eventId;
      const outcomeId = wrapper?.dataset.selectedOutcomeId;
      const stake = wrapper?.querySelector(".stake-input")?.value;

      if (confirmButton.disabled || wrapper?.dataset.closed === "true") {
        renderInlineNotice(els.eventsFeedback, "Сначала укажи сумму и выбери исход, либо рынок уже закрыт.", "error");
        return;
      }

      try {
        confirmButton.disabled = true;
        renderInlineNotice(els.eventsFeedback, "");
        renderQuotePreview(wrapper, "Покупаю позицию по текущей котировке...", "loading");
        const result = await api(`/events/${eventId}/predictions`, {
          method: "POST",
          body: JSON.stringify({ outcome_id: Number(outcomeId), stake_amount: stake }),
        });
        logResult(`POST /events/${eventId}/predictions`, result);
        const selectedButton = wrapper.querySelector(`.predict-button[data-outcome-id='${outcomeId}']`);
        const updatedOutcome = result.event?.outcomes?.find((outcome) => String(outcome.id) === String(outcomeId));
        const priceMessage = updatedOutcome ? ` Новая игровая цена: ${Number(updatedOutcome.probability_pct).toFixed(1)}%.` : "";
        const sharesMessage = result.prediction?.share_quantity ? ` Куплено долей: ${Number(result.prediction.share_quantity).toFixed(3)}.` : "";
        const avgPriceMessage = result.prediction?.average_price ? ` Средняя цена: ${Number(result.prediction.average_price).toFixed(4)}.` : "";
        renderInlineNotice(els.eventsFeedback, `Прогноз принят.${sharesMessage}${avgPriceMessage}${priceMessage}`, "success");
        renderQuotePreview(
          wrapper,
          `Позиция открыта: ${selectedButton?.dataset.outcomeLabel || "исход"}, ${Number(result.prediction?.share_quantity || 0).toFixed(3)} долей по средней цене ${Number(result.prediction?.average_price || 0).toFixed(4)}.`,
          "success",
        );
        await loadMe().catch(() => undefined);
        await loadEvents().catch(() => undefined);
      } catch (error) {
        renderInlineNotice(els.eventsFeedback, error.message, "error");
        renderQuotePreview(wrapper, error.message, "error");
        updateTradeControls(wrapper);
      }
    });
  }

  if (els.plansGrid) {
    els.plansGrid.addEventListener("click", async (event) => {
      const button = event.target.closest(".checkout-button");
      if (!button) return;
      try {
        const result = await api("/billing/checkout-session", {
          method: "POST",
          body: JSON.stringify({ plan_code: button.dataset.plan }),
        });
        logResult("POST /billing/checkout-session", result);
        alert(`Mock checkout создан: ${result.checkout_session.url}`);
      } catch (error) {
        alert(error.message);
      }
    });
  }

  if (els.portfolioSearchResults) {
    els.portfolioSearchResults.addEventListener("click", async (event) => {
      const symbol = event.target.closest("[data-symbol]")?.dataset.symbol;
      if (!symbol) return;

      if (event.target.closest(".portfolio-select-button")) {
        try {
          await loadMarketAssetQuote(symbol);
        } catch (error) {
          renderInlineNotice(els.marketFocusNotice, error.message, "error");
        }
        return;
      }

      if (event.target.closest(".portfolio-watch-toggle")) {
        try {
          await togglePortfolioWatchlist(symbol);
          renderPortfolioSearchResults();
          renderMarketFocusCard();
          await loadAssets({ log: false }).catch(() => undefined);
        } catch (error) {
          renderInlineNotice(els.marketFocusNotice, error.message, "error");
        }
      }
    });
  }

  if (els.assetsList) {
    els.assetsList.addEventListener("click", async (event) => {
      const symbol = event.target.closest("[data-symbol]")?.dataset.symbol;
      if (!symbol) return;

      if (event.target.closest(".portfolio-select-button")) {
        try {
          await loadMarketAssetQuote(symbol);
        } catch (error) {
          renderInlineNotice(els.marketFocusNotice, error.message, "error");
        }
        return;
      }

      if (event.target.closest(".portfolio-watch-toggle")) {
        try {
          await togglePortfolioWatchlist(symbol);
          renderPortfolioSearchResults();
          renderMarketFocusCard();
          await loadAssets({ log: false }).catch(() => undefined);
        } catch (error) {
          renderInlineNotice(els.marketFocusNotice, error.message, "error");
        }
      }
    });
  }

  if (els.marketFocus) {
    els.marketFocus.addEventListener("click", async (event) => {
      const symbol = event.target.closest("[data-symbol]")?.dataset.symbol;
      if (!symbol) return;

      if (event.target.closest(".portfolio-refresh-quote")) {
        try {
          await loadMarketAssetQuote(symbol);
        } catch (error) {
          renderInlineNotice(els.marketFocusNotice, error.message, "error");
        }
        return;
      }

      if (event.target.closest(".portfolio-watch-toggle")) {
        try {
          await togglePortfolioWatchlist(symbol);
          renderPortfolioSearchResults();
          renderMarketFocusCard();
          await loadAssets({ log: false }).catch(() => undefined);
        } catch (error) {
          renderInlineNotice(els.marketFocusNotice, error.message, "error");
        }
      }
    });
  }

  if (els.adminPendingEventsList) {
    els.adminPendingEventsList.addEventListener("click", async (event) => {
      const button = event.target.closest(".moderate-event-button");
      if (!button) return;
      const card = button.closest(".data-card");
      const notes = card.querySelector(".moderation-notes")?.value || "";

      try {
        const result = await api(`/admin/events/${button.dataset.eventId}/moderate`, {
          method: "POST",
          body: JSON.stringify({ decision: button.dataset.decision, notes }),
        });
        logResult(`POST /admin/events/${button.dataset.eventId}/moderate`, result);
        if (button.dataset.decision === "approve") {
          renderInlineNotice(els.adminFeedback, `Событие \"${result.event.title}\" одобрено и теперь доступно другим пользователям.`, "success");
        } else {
          renderInlineNotice(els.adminFeedback, `Событие \"${result.event.title}\" отклонено и не появится в публичной ленте.`, "error");
        }
        await loadAdminPendingEvents();
        await loadAdminDashboard().catch(() => undefined);
        await loadAdminEvents().catch(() => undefined);
        await loadEvents().catch(() => undefined);
      } catch (error) {
        renderInlineNotice(els.adminFeedback, error.message, "error");
      }
    });
  }

  if (els.adminUsersList) {
    els.adminUsersList.addEventListener("submit", async (event) => {
      const form = event.target.closest(".admin-credit-form");
      if (!form) {
        return;
      }

      event.preventDefault();
      const formData = new FormData(form);
      const userId = form.dataset.userId;
      const userHandle = form.dataset.userHandle;

      try {
        renderInlineNotice(els.adminUsersFeedback, "");
        const result = await api(`/admin/users/${userId}/wallet-credit`, {
          method: "POST",
          body: JSON.stringify({
            amount: formData.get("amount"),
            note: formData.get("note"),
          }),
        });
        logResult(`POST /admin/users/${userId}/wallet-credit`, result);
        renderInlineNotice(els.adminUsersFeedback, `Баланс пользователя ${userHandle} пополнен на ${result.wallet_entry.amount}. Новый баланс: ${result.user.wallet_balance}.`, "success");
        form.reset();
        await loadAdminUsers().catch(() => undefined);
      } catch (error) {
        renderInlineNotice(els.adminUsersFeedback, error.message, "error");
      }
    });
  }

  if (els.adminEventsList) {
    els.adminEventsList.addEventListener("click", async (event) => {
      const button = event.target.closest(".resolve-event-button");
      if (!button) return;
      const wrapper = button.closest(".mini-form");
      const winningOutcomeId = wrapper.querySelector(".resolve-outcome-id")?.value;
      if (!winningOutcomeId) {
        alert("Выбери исход для резолва.");
        return;
      }

      try {
        const result = await api(`/admin/events/${button.dataset.eventId}/resolve`, {
          method: "POST",
          body: JSON.stringify({ winning_outcome_id: Number(winningOutcomeId) }),
        });
        logResult(`POST /admin/events/${button.dataset.eventId}/resolve`, result);
        await loadAdminEvents();
      } catch (error) {
        alert(error.message);
      }
    });
  }
}

async function initPageData() {
  switch (currentPage) {
    case "dashboard":
      await loadMe();
      break;
    case "events":
      await Promise.all([loadMe(), loadEvents()]);
      break;
    case "portfolio":
      await Promise.all([loadPortfolio(), loadMe()]);
      await syncPortfolioWatchlistAndAssets();
      renderPortfolioSearchResults();
      renderMarketFocusCard();
      updatePortfolioTradeEstimate();
      schedulePortfolioMarketRefresh();
      break;
    case "leaderboards":
      await Promise.all([loadBoard("predictions"), loadBoard("portfolios"), loadMe()]);
      break;
    case "social":
      await Promise.all([loadFeed(), loadMe()]);
      break;
    case "billing":
      await Promise.all([loadBillingMe(), loadPlans(), loadMe()]);
      break;
    case "admin":
      await Promise.all([loadMe(), loadAdminDashboard(), loadAdminUsers(), loadAdminEvents(), loadAdminPendingEvents()]);
      break;
    default:
      break;
  }
}

async function init() {
  if (!ensureAccess()) {
    return;
  }
  registerCommonHandlers();
  try {
    await initPageData();
  } catch (error) {
    if (error?.message) {
      console.error(error);
    }
  }
}

init();
