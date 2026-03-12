const state = {
  apiBase: localStorage.getItem("prognose.apiBase") || "/api",
  accessToken: localStorage.getItem("prognose.accessToken") || "",
  refreshToken: localStorage.getItem("prognose.refreshToken") || "",
  lastVerificationToken: localStorage.getItem("prognose.emailToken") || "",
  me: null,
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
  social: {
    currentProfileHandle: "",
    followingHandles: [],
  },
  leaderboards: {
    predictions: [],
    portfolios: [],
  },
};

const currentPage = document.body.dataset.page || "landing";
const protectedPages = new Set(["dashboard", "profile", "events", "portfolio", "leaderboards", "social", "billing", "admin"]);

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
  socialFeedback: document.getElementById("social-feedback"),
  socialInboxMeta: document.getElementById("social-inbox-meta"),
  socialInboxList: document.getElementById("social-inbox-list"),
  publicProfileJson: document.getElementById("public-profile-json"),
  publicProfileCard: document.getElementById("public-profile-card"),
  profilePageHeading: document.getElementById("profile-page-heading"),
  profilePageCopy: document.getElementById("profile-page-copy"),
  profileEditorPanel: document.getElementById("profile-editor-panel"),
  profileEditorForm: document.getElementById("profile-editor-form"),
  profileEditorFeedback: document.getElementById("profile-editor-feedback"),
  socialDiscoveryRecommended: document.getElementById("social-discovery-recommended"),
  socialDiscoveryFollowing: document.getElementById("social-discovery-following"),
  socialTopPredictions: document.getElementById("social-top-predictions"),
  socialTopPortfolios: document.getElementById("social-top-portfolios"),
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
  const previous = els.activityLog.textContent === "Protokoll noch leer." ? "" : els.activityLog.textContent;
  els.activityLog.textContent = line + previous;
}

function translateErrorMessage(message) {
  const translations = {
    "Email is already registered.": "Diese E-Mail ist bereits registriert.",
    "Handle is already taken.": "Dieser Handle ist bereits vergeben.",
    "Invalid credentials.": "Ungueltige Anmeldedaten.",
    "User not found.": "Nutzer nicht gefunden.",
    "Profile not found.": "Profil nicht gefunden.",
    "Website URL must start with http:// or https://": "Die Website-URL muss mit http:// oder https:// beginnen.",
    "HTTP 400": "Ungueltige Anfrage.",
    "HTTP 401": "Nicht autorisiert.",
    "HTTP 403": "Zugriff verweigert.",
    "HTTP 404": "Ressource nicht gefunden.",
    "HTTP 409": "Konflikt bei der Anfrage.",
    "HTTP 500": "Interner Serverfehler.",
  };

  return translations[message] || message;
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
    throw new Error(translateErrorMessage(data.error || `HTTP ${response.status}`));
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
    return "k. A.";
  }
  const prefix = numeric > 0 ? "+" : "";
  return `${prefix}${numeric.toFixed(digits)}${suffix}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function getProfileUrl(handle) {
  return `/profile?handle=${encodeURIComponent(String(handle || "").trim().toLowerCase())}`;
}

function profileLinkMarkup(handle, label) {
  const normalizedHandle = String(handle || "").trim().toLowerCase();
  if (!normalizedHandle) {
    return escapeHtml(label || "unbekannt");
  }
  return `<a class="profile-link" href="${getProfileUrl(normalizedHandle)}">${escapeHtml(label || normalizedHandle)}</a>`;
}

function getProfileQueryHandle() {
  return new URLSearchParams(window.location.search).get("handle")?.trim().toLowerCase() || "";
}

function formatDateTime(value) {
  if (!value) {
    return "k. A.";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("de-DE");
}

function formatDate(value) {
  if (!value) {
    return "k. A.";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("de-DE");
}

function formatRank(value) {
  if (value === null || value === undefined || value === "") {
    return "k. A.";
  }
  return `#${value}`;
}

function translateBoolean(value) {
  return value ? "Ja" : "Nein";
}

function translateStatusLabel(value) {
  const normalized = String(value || "").trim().toLowerCase();
  const translations = {
    open: "Offen",
    won: "Gewonnen",
    lost: "Verloren",
    pending: "Ausstehend",
    pending_review: "In Moderation",
    resolved: "Aufgeloest",
    read: "Gelesen",
    new: "Neu",
    unverified: "Unverifiziert",
    verified: "Verifiziert",
    buy: "Kauf",
    sell: "Verkauf",
    active: "Aktiv",
    approve: "Genehmigen",
    approved: "Genehmigt",
    reject: "Ablehnen",
    rejected: "Abgelehnt",
  };
  return translations[normalized] || value;
}

function translateRelationshipLabel(value) {
  const normalized = String(value || "").trim().toLowerCase();
  const translations = {
    you: "Ich",
    following: "Abonniert",
    discover: "Entdecken",
  };
  return translations[normalized] || value;
}

function translateMetricLabel(value) {
  const normalized = String(value || "").trim().toLowerCase();
  const translations = {
    accuracy: "Trefferquote",
    roi: "ROI",
    roi_pct: "ROI",
    sample_bonus: "Stichprobenbonus",
    return: "Rendite",
    return_pct: "Rendite",
    diversification_bonus: "Diversifikationsbonus",
    sharpe_like: "Sharpe-aehnlich",
    volatility_penalty: "Volatilitaetsabzug",
  };
  return translations[normalized] || String(value || "").replace(/_/g, " ");
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
    els.portfolioSearchResults.textContent = "Beginne mit einem Ticker oder Unternehmensnamen.";
    els.portfolioSearchResults.classList.add("empty-state");
    return;
  }

  if (!items.length) {
    els.portfolioSearchResults.textContent = "Zu dieser Suche wurden keine unterstuetzten Assets gefunden.";
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
            <button type="button" class="ghost-button portfolio-select-button" data-symbol="${asset.symbol}">Oeffnen</button>
            <button type="button" class="ghost-button portfolio-watch-toggle" data-symbol="${asset.symbol}">${isWatchedSymbol(asset.symbol) ? "Aus Watchlist entfernen" : "Zur Watchlist"}</button>
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
    els.marketFocus.textContent = "Waehle ein Asset aus Suche oder Watchlist, um Preis und Details zu sehen.";
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
        <button type="button" class="ghost-button portfolio-refresh-quote" data-symbol="${asset.symbol}">Preis aktualisieren</button>
        <button type="button" class="ghost-button portfolio-watch-toggle" data-symbol="${asset.symbol}">${isWatchedSymbol(asset.symbol) ? "Aus Watchlist entfernen" : "Zur Watchlist"}</button>
      </div>
    </div>
    <div class="market-focus-price-row">
      <strong>${formatDecimal(asset.current_price, 2)} ${asset.currency || "USD"}</strong>
      <span class="market-move ${changeClass}">${formatSignedDecimal(asset.change, 2)} · ${formatSignedDecimal(asset.change_percent, 2, "%")}</span>
    </div>
    <div class="market-focus-metrics">
      <article><span>Vortagesschluss</span><strong>${asset.previous_close ? formatDecimal(asset.previous_close, 2) : "k. A."}</strong></article>
      <article><span>Tagesrange</span><strong>${asset.day_low ? formatDecimal(asset.day_low, 2) : "k. A."} - ${asset.day_high ? formatDecimal(asset.day_high, 2) : "k. A."}</strong></article>
      <article><span>Volumen</span><strong>${asset.volume || "k. A."}</strong></article>
      <article><span>Quelle</span><strong>${asset.source || "Yahoo"}</strong></article>
    </div>
  `;
}

function renderPortfolioHoldings(items) {
  if (!els.portfolioHoldings) {
    return;
  }

  if (!items.length) {
    els.portfolioHoldings.textContent = "Noch keine offenen Positionen vorhanden.";
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
          <p>Menge ${formatDecimal(holding.quantity, 4)} · Durchschnitt ${formatDecimal(holding.average_cost, 2)}</p>
          <p>Wert ${formatDecimal(holding.market_value, 2)} · Einstand ${formatDecimal(holding.cost_basis, 2)}</p>
          <p class="market-move ${Number(holding.unrealized_pnl) >= 0 ? "is-positive" : "is-negative"}">Unrealisiert ${formatSignedDecimal(holding.unrealized_pnl, 2)}</p>
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
    els.portfolioTrades.textContent = "Noch keine Trades vorhanden.";
    els.portfolioTrades.classList.add("empty-state");
    return;
  }

  els.portfolioTrades.classList.remove("empty-state");
  els.portfolioTrades.innerHTML = items
    .map(
      (trade) => `
        <article class="table-row">
          <h4>${trade.symbol} · ${translateStatusLabel(trade.side)}</h4>
          <p>${formatDecimal(trade.quantity, 4)} Einheiten zu ${formatDecimal(trade.price, 2)}</p>
          <p>Brutto ${formatDecimal(trade.gross_amount, 2)} · ${formatDateTime(trade.created_at)}</p>
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
      `Aktueller Preis ${formatDecimal(state.portfolioMarket.selectedAsset.current_price, 2)} ${state.portfolioMarket.selectedAsset.currency || "USD"}. Gib eine Menge ein, um die Schaetzung des Trades zu sehen.`,
      "info",
    );
    return;
  }

  const estimatedGross = Number(state.portfolioMarket.selectedAsset.current_price || 0) * quantity;
  renderInlineNotice(els.marketFocusNotice, `Geschaetzter Trade-Wert: ${formatDecimal(estimatedGross, 2)} ${state.portfolioMarket.selectedAsset.currency || "USD"}.`, "info");
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
  const outcomeLabel = selectedButton?.dataset.outcomeLabel || "gewaehlter Ausgang";

  if (!selectedOutcomeId || !Number.isFinite(stake) || stake <= 0) {
    renderQuotePreview(wrapper, "Geben Sie einen Betrag ein und waehlen Sie einen Ausgang, um zu sehen, wie viele Anteile Sie zum aktuellen LMSR-Preis kaufen.");
    updateTradeControls(wrapper);
    return;
  }

  const requestId = (eventQuoteRequestSeq.get(eventId) || 0) + 1;
  eventQuoteRequestSeq.set(eventId, requestId);
  renderQuotePreview(wrapper, "Quote wird berechnet...", "loading");

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
      `Kauf ${outcomeLabel}: ≈ ${shareQuantity} Anteile zum Durchschnittspreis ${averagePrice}. Nach dem Trade liegt die Spielwahrscheinlichkeit bei etwa ${postTradeProbability}%.`,
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
  state.me = payload;
  toggleAdminLinks(Boolean(payload.is_admin));
  renderMetricCards(els.accountMetrics, [
    ["Nutzername", payload.handle],
    ["Profil", payload.profile?.display_name || "nicht gesetzt"],
    ["Guthaben", payload.wallet.current_balance],
    ["Abo", payload.subscription.plan.code],
    ["Community-Postfach", payload.social.unread_notifications_count],
    ["E-Mail bestaetigt", translateBoolean(payload.email_verified)],
    ["Fehlversuche", payload.account_flags.failed_login_attempts],
    ["Verdaechtig", translateBoolean(payload.account_flags.suspicious_activity)],
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
    els.myCreatedEventsList.textContent = "Du hast noch keine Ereignisse erstellt.";
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
            <span class="position-badge is-${event.status}">${translateStatusLabel(event.status)}</span>
          </div>
          <p>${event.category} · schliesst ${formatDateTime(event.closes_at)}</p>
          <p>${event.status === "pending_review" ? "Wartet auf die Freigabe durch den Admin und ist fuer andere Nutzer noch nicht sichtbar." : "Das Ereignis ist bereits aktiv oder abgeschlossen."}</p>
          <p>${event.moderation_notes ? `Moderationshinweis: ${event.moderation_notes}` : "Keine Moderationshinweise"}</p>
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
    els.myPositionsList.textContent = "Du hast noch keine offenen oder abgeschlossenen Positionen.";
    els.myPositionsList.classList.add("empty-state");
    return;
  }

  if (!items.length) {
    els.myPositionsList.textContent = "Fuer den aktuellen Filter wurden keine Positionen gefunden.";
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
            <span class="position-badge is-${position.status}">${translateStatusLabel(position.status)}</span>
          </div>
          <p>${position.outcome_label} · Einsatz ${formatDecimal(position.stake_amount, 2)} · Anteile ${formatDecimal(position.share_quantity, 3)}</p>
          <p>Durchschnittspreis ${formatDecimal(position.average_price, 4)} · Ereignis ${translateStatusLabel(position.event_status)}</p>
          <p>${position.payout_amount && Number(position.payout_amount) > 0 ? `Auszahlung ${formatDecimal(position.payout_amount, 2)}` : "Die Auszahlung wurde noch nicht festgeschrieben"}</p>
          <p>${formatDateTime(position.created_at)}</p>
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
    els.eventsList.textContent = "Noch keine Ereignisse vorhanden.";
    els.eventsList.classList.add("empty-state");
    return;
  }

  els.eventsList.classList.remove("empty-state");
  els.eventsList.innerHTML = items
    .map(
      (event) => `
        ${(() => {
          const isClosed = event.status !== "open" || new Date(event.closes_at) <= new Date();
          const stateLabel = isClosed ? "Einsaetze geschlossen" : "Prognose moeglich";
          const marketSummary = event.market_state?.outcomes?.length
            ? `<div class="market-summary">${event.market_state.outcomes
                .map((outcome) => `<span>${outcome.label}: ${Number(outcome.probability_pct).toFixed(1)}%</span>`)
                .join("")}</div>`
            : "";
          return `
        <article class="data-card">
          <h4>${event.title}</h4>
          <p>${event.category} · ${translateStatusLabel(event.status)}</p>
          <p>${event.description || "Keine Beschreibung"}</p>
          <p>Schliesst: ${formatDateTime(event.closes_at)}</p>
          <p class="event-state ${isClosed ? "is-closed" : "is-open"}">${stateLabel}</p>
          ${marketSummary}
          <div class="mini-form trade-form" data-event-id="${event.id}" data-closed="${isClosed ? "true" : "false"}" data-selected-outcome-id="">
            <input type="number" step="0.01" min="1" placeholder="Prognosebetrag" class="stake-input" ${isClosed ? "disabled" : ""}>
            <div class="outcomes">
              ${event.outcomes
                .map(
                  (outcome) => `<button type="button" class="predict-button" data-event-id="${event.id}" data-outcome-id="${outcome.id}" data-outcome-label="${outcome.label}" ${isClosed ? "disabled" : ""}>${outcome.label} · ${Number(outcome.probability_pct).toFixed(1)}%</button>`,
                )
                .join("")}
            </div>
            <div class="quote-preview" data-role="quote-preview" data-tone="idle">Geben Sie einen Betrag ein und waehlen Sie einen Ausgang, um zu sehen, wie viele Anteile Sie zum aktuellen LMSR-Preis kaufen.</div>
            <button type="button" class="confirm-predict-button" data-closed="${isClosed ? "true" : "false"}" disabled>Positionskauf bestaetigen</button>
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
    els.assetsList.textContent = "Merke Assets aus der Suche, um dein Markt-Dashboard aufzubauen.";
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
          <p>${asset.exchange || "k. A."}</p>
          <p><strong>${formatDecimal(asset.current_price, 2)} ${asset.currency || "USD"}</strong></p>
          <p class="market-move ${Number(asset.change || 0) >= 0 ? "is-positive" : "is-negative"}">${formatSignedDecimal(asset.change, 2)} · ${formatSignedDecimal(asset.change_percent, 2, "%")}</p>
          <div class="inline-actions">
            <button type="button" class="ghost-button portfolio-select-button" data-symbol="${asset.symbol}">Oeffnen</button>
            <button type="button" class="ghost-button portfolio-watch-toggle" data-symbol="${asset.symbol}">Entfernen</button>
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
    ["Marktwert", payload.summary.market_value],
    ["Rendite %", payload.summary.return_pct],
    ["Realisierter PnL", payload.summary.realized_pnl],
    ["Unrealisierter PnL", payload.summary.unrealized_pnl],
    ["Bargeld", payload.summary.available_cash],
    ["Positionen", payload.summary.open_positions_count],
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
    element.textContent = "Die Rangliste ist noch leer.";
    element.classList.add("empty-state");
    return;
  }
  element.classList.remove("empty-state");
  element.innerHTML = items
    .map((row) => {
      const isSelf = state.me?.handle === row.handle;
      const isFollowing = state.social.followingHandles.includes(row.handle);
      const displayName = row.display_name || `@${row.handle}`;
      const bio = row.bio || "Dieser Nutzer hat noch keine Beschreibung hinzugefuegt.";
      const actionButton = isSelf
        ? ""
        : `<button type="button" class="ghost-button social-follow-button leaderboard-follow-button" data-handle="${row.handle}" data-action="${isFollowing ? "unfollow" : "follow"}">${isFollowing ? "Abo entfernen" : "Abonnieren"}</button>`;

      return `
        <article class="table-row leaderboard-row-link" data-profile-handle="${row.handle}">
          <div class="position-card-head">
            <div>
              <h4>#${row.rank} · ${profileLinkMarkup(row.handle, displayName)}</h4>
              <p>@${escapeHtml(row.handle)} · Abonnenten ${row.followers_count ?? 0}</p>
            </div>
            <span class="position-badge ${isSelf ? "is-open" : isFollowing ? "is-open" : "is-pending"}">${translateRelationshipLabel(isSelf ? "you" : isFollowing ? "following" : "discover")}</span>
          </div>
          <p class="leaderboard-row-bio">${escapeHtml(bio)}</p>
          <p>Punktzahl: ${row.score}</p>
          <p>${Object.entries(row.metrics)
            .slice(0, 3)
            .map(([key, value]) => `${translateMetricLabel(key)}: ${value}`)
            .join(" · ")}</p>
          <div class="inline-actions leaderboard-row-actions">
            <a class="hero-link secondary-link" href="${getProfileUrl(row.handle)}">Profil oeffnen</a>
            ${actionButton}
          </div>
        </article>
      `;
    })
    .join("");
}

async function loadBoard(type) {
  const payload = await api(`/leaderboards/${type}?refresh=true`, { skipAuth: true });
  state.leaderboards[type] = payload.items || [];
  renderBoard(type === "predictions" ? els.predictionBoard : els.portfolioBoard, payload.items);
  logResult(`GET /leaderboards/${type}`, payload);
}

function renderFeed(items) {
  if (!els.feedList) {
    return;
  }
  if (!items.length) {
    els.feedList.textContent = "Der Feed ist noch leer.";
    els.feedList.classList.add("empty-state");
    return;
  }
  els.feedList.classList.remove("empty-state");
  els.feedList.innerHTML = items
    .map(
      (item) => {
        if (item.type === "event") {
          return `
            <article class="data-card social-feed-card">
              <div class="position-card-head">
                <h4>${profileLinkMarkup(item.handle, item.handle || "unbekannt")}</h4>
                <span class="position-badge is-${item.event_status || "open"}">${translateStatusLabel(item.event_status || "open")}</span>
              </div>
              <p class="social-feed-title">Neuen Markt eroeffnet: ${escapeHtml(item.event_title)}</p>
              <p>${escapeHtml(item.category || "Markt")} · schliesst ${formatDateTime(item.closes_at)}</p>
              <p>${formatDateTime(item.created_at)}</p>
            </article>
          `;
        }

        return `
          <article class="data-card social-feed-card">
            <div class="position-card-head">
              <h4>${profileLinkMarkup(item.handle, item.handle || "unbekannt")}</h4>
              <span class="position-badge is-${item.status || "open"}">${translateStatusLabel(item.status || "open")}</span>
            </div>
            <p class="social-feed-title">${escapeHtml(item.event_title || "Prognose")}</p>
            <p>${escapeHtml(item.outcome || "Ausgang")} · ${item.stake_amount} Spiel-Euros</p>
            <p>${formatDateTime(item.created_at)}</p>
          </article>
        `;
      },
    )
    .join("");
}

async function loadFeed() {
  const payload = await api("/social/feed");
  renderFeed(payload.items);
  logResult("GET /social/feed", payload);
}

function renderSocialInbox(items) {
  if (!els.socialInboxList) {
    return;
  }

  const unreadCount = items.filter((item) => !item.is_read).length;
  if (els.socialInboxMeta) {
    els.socialInboxMeta.textContent = unreadCount > 0 ? `${unreadCount} ungelesen` : "Alles gelesen";
  }

  if (!items.length) {
    els.socialInboxList.textContent = "Das Postfach ist noch leer. Wenn dir jemand folgt oder Autoren aus deinem Kreis einen Markt eroeffnen, erscheint das hier.";
    els.socialInboxList.classList.add("empty-state");
    return;
  }

  els.socialInboxList.classList.remove("empty-state");
  els.socialInboxList.innerHTML = items
    .map((item) => {
      const payload = item.payload || {};
      let title = "Community-Update";
      let body = "";

      if (item.notification_type === "new_follower") {
        title = `${profileLinkMarkup(item.actor_handle || payload.follower_handle || "user", `@${item.actor_handle || payload.follower_handle || "user"}`)} hat dich abonniert`;
        body = "Ein neuer Abonnent ist in deinem sozialen Umfeld erschienen.";
      } else if (item.notification_type === "event_moderated") {
        title = `Moderation des Ereignisses: ${escapeHtml(payload.event_title || "Unbenannter Markt")}`;
        body = payload.decision === "approve"
          ? "Das Ereignis wurde freigegeben und ist jetzt oeffentlich."
          : `Das Ereignis wurde abgelehnt.${payload.moderation_notes ? ` Grund: ${escapeHtml(payload.moderation_notes)}` : ""}`;
      } else if (item.notification_type === "followed_user_event_published") {
        title = `${profileLinkMarkup(item.actor_handle || "user", `@${item.actor_handle || "user"}`)} hat einen neuen Markt eroeffnet`;
        body = `${escapeHtml(payload.event_title || "Unbenannter Markt")}${payload.category ? ` · ${escapeHtml(payload.category)}` : ""}`;
      }

      return `
        <article class="data-card social-inbox-card ${item.is_read ? "is-read" : "is-unread"}">
          <div class="position-card-head">
            <div>
              <h4>${title}</h4>
              <p>${body}</p>
            </div>
            <span class="position-badge ${item.is_read ? "is-pending" : "is-open"}">${item.is_read ? "Gelesen" : "Neu"}</span>
          </div>
          <p>${formatDateTime(item.created_at)}</p>
          ${item.is_read ? "" : `<div class="inline-actions"><button type="button" class="ghost-button social-mark-read-button" data-notification-id="${item.id}">Als gelesen markieren</button></div>`}
        </article>
      `;
    })
    .join("");
}

async function loadSocialInbox() {
  const payload = await api("/social/inbox");
  renderSocialInbox(payload.items || []);
  logResult("GET /social/inbox", payload);
  return payload.items || [];
}

async function markSocialInboxItemRead(notificationId) {
  const payload = await api(`/social/inbox/${notificationId}/read`, { method: "POST" });
  logResult(`POST /social/inbox/${notificationId}/read`, payload);
  await Promise.all([loadSocialInbox(), loadMe().catch(() => undefined)]);
}

async function markAllSocialInboxRead() {
  const payload = await api("/social/inbox/read-all", { method: "POST" });
  logResult("POST /social/inbox/read-all", payload);
  await Promise.all([loadSocialInbox(), loadMe().catch(() => undefined)]);
}

function renderSocialUserList(element, items, emptyMessage) {
  if (!element) {
    return;
  }

  if (!items.length) {
    element.textContent = emptyMessage;
    element.classList.add("empty-state");
    return;
  }

  element.classList.remove("empty-state");
  element.innerHTML = items
    .map(
      (user) => `
        <article class="data-card social-user-card">
          <div class="position-card-head">
            <div>
              <h4>${profileLinkMarkup(user.handle, user.display_name || `@${user.handle}`)}</h4>
              <p>@${escapeHtml(user.handle)} · ${escapeHtml(translateStatusLabel(user.verification_status || "unverified"))}${user.reason ? ` · ${escapeHtml(user.reason)}` : ""}</p>
            </div>
            <span class="position-badge ${user.is_following ? "is-open" : "is-pending"}">${translateRelationshipLabel(user.is_self ? "you" : user.is_following ? "following" : "discover")}</span>
          </div>
          <div class="market-summary social-summary-tags">
            <span>Abonnenten ${user.followers_count}</span>
            <span>Prognosen ${user.prediction_count}</span>
            <span>Ereignisse ${user.approved_events_count}</span>
          </div>
          <p>Prognose-Rang ${formatRank(user.leaderboards?.predictions?.rank)} · Portfolio-Rang ${formatRank(user.leaderboards?.portfolios?.rank)}</p>
          <div class="inline-actions">
            <button type="button" class="ghost-button social-profile-button" data-handle="${user.handle}">Profil</button>
            ${user.is_self ? "" : `<button type="button" class="ghost-button social-follow-button" data-handle="${user.handle}" data-action="${user.is_following ? "unfollow" : "follow"}">${user.is_following ? "Abo entfernen" : "Abonnieren"}</button>`}
          </div>
        </article>
      `,
    )
    .join("");
}

function renderSocialProfile(profile) {
  if (!els.publicProfileCard) {
    return;
  }

  if (!profile) {
    els.publicProfileCard.textContent = "Waehle einen Nutzer, um sein oeffentliches Profil und eine Kurzstatistik zu sehen.";
    els.publicProfileCard.classList.add("empty-state");
    return;
  }

  state.social.currentProfileHandle = profile.handle || "";
  const displayName = profile.display_name || `@${profile.handle}`;
  const bio = profile.bio || "Dieser Nutzer hat noch keine Beschreibung hinzugefuegt.";
  const details = [
    profile.location ? escapeHtml(profile.location) : null,
    profile.website_url ? `<a class="profile-link" href="${profile.website_url}" target="_blank" rel="noopener noreferrer">${escapeHtml(profile.website_url)}</a>` : null,
    profile.joined_at ? `Dabei seit ${formatDate(profile.joined_at)}` : null,
  ].filter(Boolean).join(" · ");
  els.publicProfileCard.classList.remove("empty-state");
  els.publicProfileCard.innerHTML = `
    <article class="data-card social-profile-card">
      <div class="position-card-head">
        <div>
          <p class="eyebrow">Oeffentliches Profil</p>
          <h4>${escapeHtml(displayName)}</h4>
          <p>@${escapeHtml(profile.handle)}</p>
        </div>
        <span class="position-badge is-${profile.verification_status || "pending"}">${translateStatusLabel(profile.verification_status || "unverified")}</span>
      </div>
      <p class="social-feed-title">${escapeHtml(bio)}</p>
      <p>${details || "Oeffentliche Profildetails sind noch nicht ausgefuellt."}</p>
      <div class="metrics-grid social-profile-metrics">
        <article class="metric-card"><span>Abonnenten</span><strong>${profile.followers_count}</strong></article>
        <article class="metric-card"><span>Folgt</span><strong>${profile.following_count}</strong></article>
        <article class="metric-card"><span>Prognosen</span><strong>${profile.prediction_count}</strong></article>
        <article class="metric-card"><span>Ereignisse</span><strong>${profile.approved_events_count || 0}</strong></article>
      </div>
      <p>Prognose-Rangliste: ${formatRank(profile.leaderboards?.predictions?.rank)} · Punktzahl ${profile.leaderboards?.predictions?.score || "k. A."}</p>
      <p>Portfolio-Rangliste: ${formatRank(profile.leaderboards?.portfolios?.rank)} · Punktzahl ${profile.leaderboards?.portfolios?.score || "k. A."}</p>
      <p>Portfolio-Rendite: ${profile.portfolio_summary?.return_pct || "0.00"}% · offene Positionen ${profile.portfolio_summary?.open_positions_count || 0}</p>
    </article>
  `;
  renderCodeBox(els.publicProfileJson, profile);
}

async function loadPublicProfile(handle, { log = true } = {}) {
  const payload = await api(`/users/${handle}`, { skipAuth: true });
  renderSocialProfile(payload.profile);
  if (log) {
    logResult(`GET /users/${handle}`, payload);
  }
  return payload.profile;
}

function renderSocialDiscovery(payload) {
  state.social.followingHandles = (payload.following || []).map((user) => user.handle);
  renderSocialUserList(els.socialDiscoveryRecommended, payload.recommended_users || [], "Noch keine Empfehlungen. Hier erscheinen Autoren aus Ranglisten und aktiven Maerkten.");
  renderSocialUserList(els.socialDiscoveryFollowing, payload.following || [], "Du hast noch niemanden abonniert.");
  renderSocialUserList(els.socialTopPredictions, payload.top_prediction_users || [], "Die Prognose-Rangliste ist noch leer.");
  renderSocialUserList(els.socialTopPortfolios, payload.top_portfolio_users || [], "Die Portfolio-Rangliste ist noch leer.");
}

async function loadSocialDiscovery() {
  const payload = await api("/social/discovery");
  renderSocialDiscovery(payload);
  logResult("GET /social/discovery", payload);
  return payload;
}

async function updateSocialFollow(handle, action) {
  const method = action === "unfollow" ? "DELETE" : "POST";
  const result = await api(`/users/${handle}/follow`, { method });
  logResult(`${method} /users/${handle}/follow`, result);
  renderInlineNotice(els.socialFeedback, action === "unfollow" ? `Das Abo fuer @${handle} wurde entfernt.` : `Du hast @${handle} jetzt abonniert.`, "success");
  await Promise.all([loadFeed(), loadSocialDiscovery()]);
  if (currentPage === "leaderboards") {
    renderBoard(els.predictionBoard, state.leaderboards.predictions || []);
    renderBoard(els.portfolioBoard, state.leaderboards.portfolios || []);
  }
  if (state.social.currentProfileHandle && state.social.currentProfileHandle === handle) {
    await loadPublicProfile(handle, { log: false }).catch(() => undefined);
  }
}

function populateProfileEditor(profile, handle) {
  if (!els.profileEditorForm) {
    return;
  }

  const displayNameInput = els.profileEditorForm.querySelector("[name='display_name']");
  const bioInput = els.profileEditorForm.querySelector("[name='bio']");
  const locationInput = els.profileEditorForm.querySelector("[name='location']");
  const websiteInput = els.profileEditorForm.querySelector("[name='website_url']");
  const handleInput = els.profileEditorForm.querySelector("[name='handle_readonly']");

  if (displayNameInput) displayNameInput.value = profile?.display_name || "";
  if (bioInput) bioInput.value = profile?.bio || "";
  if (locationInput) locationInput.value = profile?.location || "";
  if (websiteInput) websiteInput.value = profile?.website_url || "";
  if (handleInput) handleInput.value = handle || "";
}

function renderProfilePageMeta(profile, isSelf) {
  if (els.profilePageHeading) {
    els.profilePageHeading.textContent = isSelf ? "Mein Profil" : `Profil @${profile.handle}`;
  }
  if (els.profilePageCopy) {
    els.profilePageCopy.textContent = isSelf
      ? "Fuege Informationen ueber dich hinzu: Sie werden in Empfehlungen, Nutzerkarten und im oeffentlichen Profil angezeigt."
      : "Oeffentliches Profil eines Teilnehmers mit kurzer sozialer und spielerischer Statistik.";
  }
  if (els.profileEditorPanel) {
    els.profileEditorPanel.classList.toggle("is-hidden", !isSelf);
  }
}

async function saveMyProfile(form) {
  const formData = new FormData(form);
  const payload = {
    display_name: formData.get("display_name"),
    bio: formData.get("bio"),
    location: formData.get("location"),
    website_url: formData.get("website_url"),
  };

  const result = await api("/me/profile", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  logResult("PATCH /me/profile", result);
  renderInlineNotice(els.profileEditorFeedback, "Profil aktualisiert.", "success");
  await loadMe();
  await loadPublicProfile(state.me?.handle || result.handle, { log: false });
}

async function loadProfilePage() {
  const me = await loadMe();
  const requestedHandle = getProfileQueryHandle() || me.handle;
  const profile = await loadPublicProfile(requestedHandle, { log: false });
  const isSelf = requestedHandle === me.handle;

  renderProfilePageMeta(profile, isSelf);
  populateProfileEditor(me.profile, me.handle);
  renderCodeBox(els.publicProfileJson, profile);
}

function renderPlans(items) {
  if (!els.plansGrid) {
    return;
  }
  if (!items.length) {
    els.plansGrid.textContent = "Tarife sind derzeit nicht verfuegbar.";
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
          <p>${plan.monthly_price} ${plan.currency}/Monat</p>
          <p>Max. Abos: ${plan.entitlements.max_follows}</p>
          <p>Erweiterte Analysen: ${translateBoolean(plan.entitlements.advanced_analytics)}</p>
          ${plan.code === "free" ? "" : `<button class="checkout-button" data-plan="${plan.code}">Test-Kauf</button>`}
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
    ["Tarif", subscription.plan.code],
    ["Status", translateStatusLabel(subscription.status)],
    ["Seit", subscription.started_at ? formatDate(subscription.started_at) : "k. A."],
    ["Max. Abos", subscription.entitlements.max_follows],
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
    els.adminUsersList.textContent = "Nutzer wurden noch nicht geladen.";
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
          <p>Admin: ${translateBoolean(user.is_admin)} · bestaetigt: ${translateBoolean(user.email_verified)}</p>
          <p>Fehlversuche: ${user.failed_login_attempts} · verdaechtig: ${translateBoolean(user.suspicious_activity)}</p>
          <p>Guthaben: ${user.wallet_balance ?? "k. A."}</p>
          <form class="mini-form admin-credit-form" data-user-id="${user.id}" data-user-handle="${user.handle}">
            <input name="amount" type="number" step="0.01" min="0.01" placeholder="Betrag fuer Aufladung" required>
            <input name="note" type="text" maxlength="120" placeholder="Grund, zum Beispiel Support-Gutschrift">
            <button type="submit">Guthaben aufladen</button>
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
    els.adminEventsList.textContent = "Ereignisse wurden noch nicht geladen.";
    els.adminEventsList.classList.add("empty-state");
    return;
  }

  els.adminEventsList.classList.remove("empty-state");
  els.adminEventsList.innerHTML = items
    .map(
      (event) => `
        <article class="data-card">
          <h4>#${event.id} · ${event.title}</h4>
          <p>${event.category} · ${translateStatusLabel(event.status)}</p>
          <p>Ersteller: ${event.creator_id}</p>
          <div class="mini-form" data-admin-event-id="${event.id}">
            <select class="resolve-outcome-id">
              <option value="">Ausgang fuer Aufloesung waehlen</option>
              ${event.outcomes
                .map((outcome) => `<option value="${outcome.id}">${outcome.label}</option>`)
                .join("")}
            </select>
            <button type="button" class="resolve-event-button" data-event-id="${event.id}">Aufloesen</button>
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
    els.adminPendingEventsList.textContent = "Die Moderationswarteschlange ist leer.";
    els.adminPendingEventsList.classList.add("empty-state");
    return;
  }

  els.adminPendingEventsList.classList.remove("empty-state");
  els.adminPendingEventsList.innerHTML = items
    .map(
      (event) => `
        <article class="data-card">
          <h4>#${event.id} · ${event.title}</h4>
          <p>${event.category} · Ersteller ${event.creator_id}</p>
          <p>${event.description || "Keine Beschreibung"}</p>
          <p>Quelle: ${event.source_of_truth}</p>
          <p>Ausgaenge: ${event.outcomes.map((outcome) => outcome.label).join(", ")}</p>
          <textarea class="moderation-notes" placeholder="Begruendung der Entscheidung"></textarea>
          <div class="inline-actions">
            <button type="button" class="moderate-event-button" data-event-id="${event.id}" data-decision="approve">Freigeben</button>
            <button type="button" class="ghost-button moderate-event-button" data-event-id="${event.id}" data-decision="reject">Ablehnen</button>
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
    els.adminAiResults.textContent = "Die KI-Generierung hat keine Kandidaten geliefert. Probiere andere Themen oder Quellen.";
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
            <span class="position-badge is-${item.publication_status}">${translateStatusLabel(item.publication_status)}</span>
          </div>
          <p>${item.category} · Konfidenz ${formatDecimal(item.confidence, 2)}</p>
          <p>${item.selection_reason || item.rationale || "Keine Begruendung des Modells vorhanden"}</p>
          <p>Aufloesungsquelle: ${item.source_of_truth}</p>
          <p>Fenster: ${formatDateTime(item.closes_at)} -> ${formatDateTime(item.resolves_at)}</p>
          <p>KI-Einschaetzung: ${item.recommended_outcome} · Einsatz ${formatDecimal(item.recommended_stake, 2)}</p>
          <p>${item.event_id ? `Als Ereignis #${item.event_id} mit Status ${translateStatusLabel(item.event_status || item.publication_status)} erstellt` : "Noch nicht erstellt"}</p>
          <p>${item.seed_prediction?.status === "created" ? `Bot hat ${item.seed_prediction.outcome_label} mit ${item.seed_prediction.stake_amount} gesetzt` : (item.seed_prediction?.reason || "Keine KI-Startposition")}</p>
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
    ["Nutzer", payload.users_total],
    ["Administratoren", payload.admins_total],
    ["Ausstehend", payload.pending_events],
    ["Offene Ereignisse", payload.open_events],
    ["Aufgeloest", payload.resolved_events],
    ["Verdaechtig", payload.suspicious_users],
    ["Instrumente", payload.assets_total],
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
      els.activityLog.textContent = "Protokoll noch leer.";
    }
  });

  bind("refresh-access", "click", async () => {
    if (!state.refreshToken) {
      alert("Bitte melde dich zuerst an.");
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
  bind("load-social-inbox", "click", () => loadSocialInbox().catch((error) => renderInlineNotice(els.socialFeedback, error.message, "error")));
  bind("mark-all-social-read", "click", () => markAllSocialInboxRead().catch((error) => renderInlineNotice(els.socialFeedback, error.message, "error")));
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
        renderInlineNotice(els.eventsFeedback, "Das Ereignis wurde erstellt und zur Moderation an den Admin gesendet.", "info");
      } else {
        renderInlineNotice(els.eventsFeedback, "Das Ereignis wurde erstellt und ist bereits fuer Prognosen geoeffnet.", "success");
      }
      await loadEvents();
    } catch (error) {
      renderInlineNotice(els.eventsFeedback, error.message, "error");
    }
  });

  bind("trade-form", "submit", async (event) => {
    try {
      if (!state.portfolioMarket.selectedAsset?.symbol) {
        throw new Error("Bitte waehle zuerst ein Asset aus der Suche oder der Watchlist.");
      }

      renderInlineNotice(els.marketFocusNotice, "");
      await submitJsonForm(event, "/portfolio/trades", (formData) => ({
        symbol: formData.get("symbol"),
        side: formData.get("side"),
        quantity: formData.get("quantity"),
      }));
      renderInlineNotice(els.marketFocusNotice, `Der Trade fuer ${state.portfolioMarket.selectedAsset.symbol} wurde uebermittelt und im Portfolio gespeichert.`, "success");
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
      renderInlineNotice(els.socialFeedback, "");
      await updateSocialFollow(handle, "follow");
      event.currentTarget.reset();
    } catch (error) {
      renderInlineNotice(els.socialFeedback, error.message, "error");
    }
  });

  bind("profile-form", "submit", async (event) => {
    event.preventDefault();
    const handle = new FormData(event.currentTarget).get("handle");
    try {
      window.location.href = getProfileUrl(handle);
    } catch (error) {
      renderInlineNotice(els.socialFeedback, error.message, "error");
    }
  });

  bind("profile-editor-form", "submit", async (event) => {
    event.preventDefault();
    try {
      renderInlineNotice(els.profileEditorFeedback, "");
      await saveMyProfile(event.currentTarget);
    } catch (error) {
      renderInlineNotice(els.profileEditorFeedback, error.message, "error");
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
      renderInlineNotice(els.adminAiFeedback, "Gib ein Thema an und fuege mindestens eine URL oder eine kurze Notiz aus dem Browser hinzu.", "error");
      return;
    }

    if (rawSourceNotes.length > 6000) {
      renderInlineNotice(els.adminAiFeedback, "Die Quellenhinweise sind zu lang. Lass nur einige kurze Absaetze oder Stichpunkte stehen, maximal 6000 Zeichen.", "error");
      return;
    }

    try {
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = "Generierung...";
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
      const warningMessage = (result.warnings || []).length ? ` Warnungen: ${(result.warnings || []).join(" | ")}` : "";
      renderInlineNotice(
        els.adminAiFeedback,
        `Die KI-Generierung ist abgeschlossen. Modell ${result.used_model} hat ${(result.items || []).length} Kandidaten geliefert.${warningMessage}`,
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
        submitButton.textContent = "KI-Generierung starten";
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
        renderQuotePreview(wrapper, "Der Betrag ist gesetzt. Waehle jetzt einen Ausgang, um eine Quote zu erhalten.");
      }
    });

    els.eventsList.addEventListener("click", async (event) => {
      const outcomeButton = event.target.closest(".predict-button");
      if (outcomeButton) {
        const wrapper = outcomeButton.closest(".trade-form");
        if (outcomeButton.disabled || wrapper?.dataset.closed === "true") {
          renderInlineNotice(els.eventsFeedback, "Die Prognose ist nicht verfuegbar: Der Markt ist zeitlich oder per Status bereits geschlossen.", "error");
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
        renderInlineNotice(els.eventsFeedback, "Gib zuerst einen Betrag ein und waehle einen Ausgang, oder der Markt ist bereits geschlossen.", "error");
        return;
      }

      try {
        confirmButton.disabled = true;
        renderInlineNotice(els.eventsFeedback, "");
        renderQuotePreview(wrapper, "Position wird zur aktuellen Quote gekauft...", "loading");
        const result = await api(`/events/${eventId}/predictions`, {
          method: "POST",
          body: JSON.stringify({ outcome_id: Number(outcomeId), stake_amount: stake }),
        });
        logResult(`POST /events/${eventId}/predictions`, result);
        const selectedButton = wrapper.querySelector(`.predict-button[data-outcome-id='${outcomeId}']`);
        const updatedOutcome = result.event?.outcomes?.find((outcome) => String(outcome.id) === String(outcomeId));
        const priceMessage = updatedOutcome ? ` Neuer Spielpreis: ${Number(updatedOutcome.probability_pct).toFixed(1)}%.` : "";
        const sharesMessage = result.prediction?.share_quantity ? ` Gekaufte Anteile: ${Number(result.prediction.share_quantity).toFixed(3)}.` : "";
        const avgPriceMessage = result.prediction?.average_price ? ` Durchschnittspreis: ${Number(result.prediction.average_price).toFixed(4)}.` : "";
        renderInlineNotice(els.eventsFeedback, `Prognose angenommen.${sharesMessage}${avgPriceMessage}${priceMessage}`, "success");
        renderQuotePreview(
          wrapper,
          `Position eroeffnet: ${selectedButton?.dataset.outcomeLabel || "Ausgang"}, ${Number(result.prediction?.share_quantity || 0).toFixed(3)} Anteile zum Durchschnittspreis ${Number(result.prediction?.average_price || 0).toFixed(4)}.`,
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
        alert(`Test-Kauf erstellt: ${result.checkout_session.url}`);
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

  if (els.feedList || els.socialDiscoveryRecommended || els.socialDiscoveryFollowing || els.publicProfileCard) {
    document.addEventListener("click", async (event) => {
      const markReadButton = event.target.closest(".social-mark-read-button");
      if (markReadButton) {
        try {
          renderInlineNotice(els.socialFeedback, "");
          await markSocialInboxItemRead(markReadButton.dataset.notificationId);
        } catch (error) {
          renderInlineNotice(els.socialFeedback, error.message, "error");
        }
        return;
      }

      const profileButton = event.target.closest(".social-profile-button");
      if (profileButton) {
        try {
          window.location.href = getProfileUrl(profileButton.dataset.handle);
        } catch (error) {
          renderInlineNotice(els.socialFeedback, error.message, "error");
        }
        return;
      }

      const followButton = event.target.closest(".social-follow-button");
      if (!followButton) {
        return;
      }

      try {
        renderInlineNotice(els.socialFeedback, "");
        await updateSocialFollow(followButton.dataset.handle, followButton.dataset.action);
      } catch (error) {
        renderInlineNotice(els.socialFeedback, error.message, "error");
      }
    });
  }

  [els.predictionBoard, els.portfolioBoard].filter(Boolean).forEach((boardElement) => {
    boardElement.addEventListener("click", async (event) => {
      const followButton = event.target.closest(".leaderboard-follow-button");
      if (followButton) {
        event.preventDefault();
        event.stopPropagation();
        try {
          await updateSocialFollow(followButton.dataset.handle, followButton.dataset.action);
        } catch (error) {
          alert(error.message);
        }
        return;
      }

      const row = event.target.closest(".leaderboard-row-link[data-profile-handle]");
      if (!row) {
        return;
      }

      const directLink = event.target.closest("a");
      if (directLink) {
        return;
      }

      window.location.href = getProfileUrl(row.dataset.profileHandle);
    });
  });

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
          renderInlineNotice(els.adminFeedback, `Das Ereignis \"${result.event.title}\" wurde freigegeben und ist jetzt fuer andere Nutzer sichtbar.`, "success");
        } else {
          renderInlineNotice(els.adminFeedback, `Das Ereignis \"${result.event.title}\" wurde abgelehnt und erscheint nicht im oeffentlichen Feed.`, "error");
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
        renderInlineNotice(els.adminUsersFeedback, `Das Guthaben von ${userHandle} wurde um ${result.wallet_entry.amount} erhoeht. Neuer Kontostand: ${result.user.wallet_balance}.`, "success");
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
        alert("Waehle einen Ausgang fuer die Aufloesung.");
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
      await Promise.all([loadMe(), loadSocialDiscovery()]);
      await Promise.all([loadBoard("predictions"), loadBoard("portfolios")]);
      break;
    case "social":
      await Promise.all([loadFeed(), loadSocialDiscovery(), loadSocialInbox(), loadMe()]);
      renderSocialProfile(null);
      break;
    case "profile":
      await loadProfilePage();
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
