/* ── Session storage (localStorage) ─────────────────────────── */
const _TOKEN_KEY = "rez_auth_token";

function _parseToken(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (payload.exp && payload.exp * 1000 < Date.now()) return null;
    return payload;
  } catch { return null; }
}

function getSession() {
  const token = localStorage.getItem(_TOKEN_KEY);
  if (!token) return null;
  const payload = _parseToken(token);
  if (!payload) { localStorage.removeItem(_TOKEN_KEY); return null; }
  return { token, user: { sub: payload.sub, email: payload.email, name: payload.name } };
}

function _storeToken(token) {
  if (!_parseToken(token)) return;
  localStorage.setItem(_TOKEN_KEY, token);
}

/* ── Handle OAuth callback token in URL ──────────────────────── */
(function handleOAuthCallback() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  if (!token) return;
  _storeToken(token);
  const url = new URL(window.location);
  url.searchParams.delete("token");
  window.history.replaceState({}, "", url);
})();

/* ── Init ────────────────────────────────────────────────────── */
(function initAuth() {
  _applySession(getSession());
  try {
    const version = null; // version loaded via /api/config separately if needed
  } catch { /* */ }
})();

/* ── Fetch version label ─────────────────────────────────────── */
(async function loadVersion() {
  try {
    const res  = await fetch("api/config");
    const data = await res.json();
    const vEl  = document.getElementById("version-label");
    if (vEl && data.version) vEl.textContent = `v${data.version}`;
  } catch { /* */ }
})();

function _applySession(session) {
  const authBtn   = document.getElementById("auth-btn");
  const userMenu  = document.getElementById("user-menu");
  const userEmail = document.getElementById("user-email");

  if (session?.user) {
    authBtn.hidden  = true;
    userMenu.hidden = false;
    userEmail.textContent = session.user.name || session.user.email || "Account";
  } else {
    authBtn.hidden  = false;
    userMenu.hidden = true;
  }
}

/* ── Modal open/close ────────────────────────────────────────── */
let _authMode = "signin";
let _modalFormHTML = null;

function openAuthModal() {
  const inner = document.getElementById("auth-modal-inner");
  if (_modalFormHTML) inner.innerHTML = _modalFormHTML;
  _modalFormHTML = null;
  _authMode = "signin";
  document.getElementById("auth-error").hidden = true;
  document.getElementById("auth-modal").hidden          = false;
  document.getElementById("auth-modal-backdrop").hidden = false;
  document.body.style.overflow = "hidden";
}

function closeAuthModal() {
  document.getElementById("auth-modal").hidden          = true;
  document.getElementById("auth-modal-backdrop").hidden = true;
  document.body.style.overflow = "";
  _modalFormHTML = null;
}

function toggleAuthMode(e) {
  e.preventDefault();
  _authMode = _authMode === "signin" ? "signup" : "signin";
  const isSignup = _authMode === "signup";
  document.getElementById("auth-submit").textContent      = isSignup ? "Sign up" : "Sign in";
  document.getElementById("auth-toggle-text").textContent = isSignup ? "Already have an account?" : "Don't have an account?";
  document.getElementById("auth-toggle-link").textContent = isSignup ? "Sign in" : "Sign up";
  document.getElementById("auth-error").hidden = true;
}

/* ── Google OAuth ────────────────────────────────────────────── */
function signInWith(provider) {
  if (provider === "google") {
    window.location.href = "api/auth/google";
  }
}

/* ── Email / password ────────────────────────────────────────── */
async function handleEmailAuth(e) {
  e.preventDefault();

  const email    = document.getElementById("auth-email").value.trim();
  const password = document.getElementById("auth-password").value;
  const errEl    = document.getElementById("auth-error");
  const btn      = document.getElementById("auth-submit");

  btn.disabled = true;
  errEl.hidden = true;

  const endpoint = _authMode === "signup" ? "api/auth/signup" : "api/auth/login";
  try {
    const res  = await fetch(endpoint, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      errEl.textContent = data.detail || "Authentication failed";
      errEl.hidden = false;
      return;
    }
    _storeToken(data.token);
    _applySession(getSession());
    closeAuthModal();
    const cookbook = document.getElementById("cookbook-section");
    if (cookbook && !cookbook.hidden) showCookbook(false);
  } catch {
    errEl.textContent = "Network error — please try again";
    errEl.hidden = false;
  } finally {
    btn.disabled = false;
  }
}

/* ── Sign out ────────────────────────────────────────────────── */
function signOut() {
  localStorage.removeItem(_TOKEN_KEY);
  _applySession(null);
}
