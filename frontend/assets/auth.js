const authState = {
  apiBase: localStorage.getItem("prognose.apiBase") || "/api",
  accessToken: localStorage.getItem("prognose.accessToken") || "",
  refreshToken: localStorage.getItem("prognose.refreshToken") || "",
  lastVerificationToken: localStorage.getItem("prognose.emailToken") || "",
};

const authResult = document.getElementById("auth-result");
const authStatus = document.getElementById("auth-status");
const authHint = document.getElementById("auth-hint");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const refreshButton = document.getElementById("refresh-access");
const verifyButton = document.getElementById("verify-email");

function showHint(message, href, linkLabel) {
  if (!authHint) {
    return;
  }
  if (!message) {
    authHint.textContent = "";
    authHint.classList.add("is-hidden");
    return;
  }

  authHint.innerHTML = href ? `${message} <a href="${href}">${linkLabel}</a>` : message;
  authHint.classList.remove("is-hidden");
}

function getStoredEmail() {
  return localStorage.getItem("prognose.lastEmail") || "";
}

function storeEmail(email) {
  const normalizedEmail = String(email || "").trim().toLowerCase();
  if (normalizedEmail) {
    localStorage.setItem("prognose.lastEmail", normalizedEmail);
  }
}

function renderAuthResult(label, payload) {
  authResult.textContent = `[${label}]\n${JSON.stringify(payload, null, 2)}`;
  authResult.classList.remove("empty-state");
}

function setStatus(text) {
  authStatus.textContent = `Статус: ${text}`;
}

async function authApi(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (authState.accessToken && !options.skipAuth) {
    headers.Authorization = `Bearer ${authState.accessToken}`;
  }

  const response = await fetch(`${authState.apiBase}${path}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function persistTokens(accessToken, refreshToken) {
  if (accessToken) {
    authState.accessToken = accessToken;
    localStorage.setItem("prognose.accessToken", accessToken);
  }
  if (refreshToken) {
    authState.refreshToken = refreshToken;
    localStorage.setItem("prognose.refreshToken", refreshToken);
  }
}

if (registerForm) {
  const emailField = registerForm.elements.namedItem("email");
  const storedEmail = getStoredEmail();
  if (emailField && storedEmail && !emailField.value) {
    emailField.value = storedEmail;
  }

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const payload = Object.fromEntries(new FormData(registerForm));
      storeEmail(payload.email);
      const result = await authApi("/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
        skipAuth: true,
      });
      authState.lastVerificationToken = result.dev_notes?.email_verification_token || "";
      localStorage.setItem("prognose.emailToken", authState.lastVerificationToken);
      setStatus("аккаунт создан");
      showHint("Аккаунт создан. Можно подтвердить email или сразу перейти ко входу.", "/login", "Перейти ко входу");
      renderAuthResult("register", result);
    } catch (error) {
      setStatus("ошибка регистрации");
      if (error.message === "Email is already registered.") {
        const email = getStoredEmail();
        const loginHref = email ? `/login?email=${encodeURIComponent(email)}` : "/login";
        showHint("Такой email уже есть в системе. Войди под ним или используй другой email для новой регистрации.", loginHref, "Открыть вход");
      } else if (error.message === "Handle is already taken.") {
        showHint("Этот handle уже занят. Выбери другой nickname для нового аккаунта.");
      } else {
        showHint("");
      }
      renderAuthResult("register-error", { error: error.message });
    }
  });
}

if (loginForm) {
  const loginEmailField = loginForm.elements.namedItem("email");
  const loginQuery = new URLSearchParams(window.location.search);
  const suggestedEmail = loginQuery.get("email") || getStoredEmail();
  if (loginEmailField && suggestedEmail && !loginEmailField.value) {
    loginEmailField.value = suggestedEmail;
  }

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const payload = Object.fromEntries(new FormData(loginForm));
      storeEmail(payload.email);
      const result = await authApi("/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
        skipAuth: true,
      });
      persistTokens(result.access_token, result.refresh_token);
      setStatus("вход выполнен");
      showHint("");
      renderAuthResult("login", result);
      window.location.href = "/dashboard";
    } catch (error) {
      setStatus("ошибка входа");
      if (error.message === "Invalid credentials.") {
        showHint("Проверь email и пароль. Если аккаунт уже создан, используй те же данные, что при регистрации.");
      } else {
        showHint("");
      }
      renderAuthResult("login-error", { error: error.message });
    }
  });
}

if (verifyButton) {
  verifyButton.addEventListener("click", async () => {
    if (!authState.lastVerificationToken) {
      setStatus("нет verification token");
      renderAuthResult("verify-error", { error: "Сначала зарегистрируй аккаунт." });
      return;
    }

    try {
      const result = await authApi("/auth/verify-email", {
        method: "POST",
        body: JSON.stringify({ token: authState.lastVerificationToken }),
        skipAuth: true,
      });
      setStatus("email подтвержден");
      showHint("Email подтвержден. Теперь можно войти в кабинет.", "/login", "Открыть вход");
      renderAuthResult("verify-email", result);
    } catch (error) {
      setStatus("ошибка подтверждения");
      renderAuthResult("verify-error", { error: error.message });
    }
  });
}

if (refreshButton) {
  refreshButton.addEventListener("click", async () => {
    if (!authState.refreshToken) {
      setStatus("нет refresh token");
      renderAuthResult("refresh-error", { error: "Сначала войди в аккаунт." });
      return;
    }

    try {
      const response = await fetch(`${authState.apiBase}/auth/refresh`, {
        method: "POST",
        headers: { Authorization: `Bearer ${authState.refreshToken}` },
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || `HTTP ${response.status}`);
      }
      persistTokens(result.access_token, null);
      setStatus("access token обновлен");
      showHint("");
      renderAuthResult("refresh", result);
    } catch (error) {
      setStatus("ошибка обновления токена");
      renderAuthResult("refresh-error", { error: error.message });
    }
  });
}