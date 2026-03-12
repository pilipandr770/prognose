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
  if (!authResult) {
    return;
  }
  authResult.textContent = `[${label}]\n${JSON.stringify(payload, null, 2)}`;
  authResult.classList.remove("empty-state");
}

function setStatus(text) {
  if (!authStatus) {
    return;
  }
  authStatus.textContent = `Status: ${text}`;
}

function translateAuthError(message) {
  const translations = {
    "Email is already registered.": "Diese E-Mail ist bereits registriert.",
    "Handle is already taken.": "Dieser Handle ist bereits vergeben.",
    "Invalid credentials.": "Ungueltige Anmeldedaten.",
    "HTTP 401": "Nicht autorisiert.",
    "HTTP 403": "Zugriff verweigert.",
    "HTTP 404": "Ressource nicht gefunden.",
    "HTTP 500": "Interner Serverfehler.",
  };

  return translations[message] || message;
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
      setStatus("Konto erstellt");
      showHint("Konto erstellt. Du kannst jetzt die E-Mail bestaetigen oder direkt zum Login wechseln.", "/login", "Zum Login");
      renderAuthResult("register", result);
    } catch (error) {
      const localizedError = translateAuthError(error.message);
      setStatus("Registrierung fehlgeschlagen");
      if (error.message === "Email is already registered.") {
        const email = getStoredEmail();
        const loginHref = email ? `/login?email=${encodeURIComponent(email)}` : "/login";
        showHint("Diese E-Mail existiert bereits. Melde dich damit an oder nutze eine andere E-Mail fuer ein neues Konto.", loginHref, "Login oeffnen");
      } else if (error.message === "Handle is already taken.") {
        showHint("Dieser Handle ist bereits belegt. Bitte waehle einen anderen Namen fuer dein neues Konto.");
      } else {
        showHint("");
      }
      renderAuthResult("register-error", { error: localizedError });
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
      setStatus("Anmeldung erfolgreich");
      showHint("");
      renderAuthResult("login", result);
      window.location.href = "/dashboard";
    } catch (error) {
      const localizedError = translateAuthError(error.message);
      setStatus("Anmeldung fehlgeschlagen");
      if (error.message === "Invalid credentials.") {
        showHint("Pruefe E-Mail und Passwort. Wenn das Konto bereits existiert, nutze dieselben Daten wie bei der Registrierung.");
      } else {
        showHint("");
      }
      renderAuthResult("login-error", { error: localizedError });
    }
  });
}

if (verifyButton) {
  verifyButton.addEventListener("click", async () => {
    if (!authState.lastVerificationToken) {
      setStatus("Kein Bestaetigungstoken vorhanden");
      renderAuthResult("verify-error", { error: "Bitte registriere zuerst ein Konto." });
      return;
    }

    try {
      const result = await authApi("/auth/verify-email", {
        method: "POST",
        body: JSON.stringify({ token: authState.lastVerificationToken }),
        skipAuth: true,
      });
      setStatus("E-Mail bestaetigt");
      showHint("Die E-Mail wurde bestaetigt. Du kannst dich jetzt anmelden.", "/login", "Login oeffnen");
      renderAuthResult("verify-email", result);
    } catch (error) {
      setStatus("Bestaetigung fehlgeschlagen");
      renderAuthResult("verify-error", { error: translateAuthError(error.message) });
    }
  });
}

if (refreshButton) {
  refreshButton.addEventListener("click", async () => {
    if (!authState.refreshToken) {
      setStatus("Kein Refresh-Token vorhanden");
      renderAuthResult("refresh-error", { error: "Bitte melde dich zuerst an." });
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
      setStatus("Zugangstoken erneuert");
      showHint("");
      renderAuthResult("refresh", result);
    } catch (error) {
      setStatus("Token-Aktualisierung fehlgeschlagen");
      renderAuthResult("refresh-error", { error: translateAuthError(error.message) });
    }
  });
}