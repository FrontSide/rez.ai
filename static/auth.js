/* ── Supabase auth ──────────────────────────────────────────── */
let _supabase = null;
let _authMode = "signin"; // "signin" | "signup"

async function getSupabase() {
  if (_supabase) return _supabase;
  const res = await fetch("api/config");
  const data = await res.json();
  const { supabase_url, supabase_anon_key, version } = data;
  if (!supabase_url || !supabase_anon_key) {
    console.warn("Supabase not configured — auth disabled");
    return null;
  }
  const vEl = document.getElementById("version-label");
  if (vEl && version) vEl.textContent = `v${version}`;
  _supabase = supabase.createClient(supabase_url, supabase_anon_key);
  return _supabase;
}

/* ── init ─────────────────────────────────────────────────── */
(async function initAuth() {
  const sb = await getSupabase();
  if (!sb) return;

  const { data: { session } } = await sb.auth.getSession();
  _applySession(session);

  sb.auth.onAuthStateChange((_event, session) => {
    _applySession(session);
    if (session) {
      closeAuthModal();
      // Refresh cookbook if it's currently visible
      const cookbook = document.getElementById("cookbook-section");
      if (cookbook && !cookbook.hidden) showCookbook(false);
    }
  });
})();

function _applySession(session) {
  const authBtn    = document.getElementById("auth-btn");
  const userMenu   = document.getElementById("user-menu");
  const userEmail  = document.getElementById("user-email");

  if (session?.user) {
    authBtn.hidden   = true;
    userMenu.hidden  = false;
    userEmail.textContent = session.user.email || session.user.user_metadata?.full_name || "Account";
  } else {
    authBtn.hidden   = false;
    userMenu.hidden  = true;
  }
}

/* ── modal open/close ─────────────────────────────────────── */
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

function _showConfirmation(email) {
  const inner = document.getElementById("auth-modal-inner");
  _modalFormHTML = inner.innerHTML;
  inner.innerHTML = `
    <h2 class="modal-title">Check your inbox</h2>
    <p class="auth-confirm-text">
      We sent a confirmation link to<br>
      <strong>${escHtml(email)}</strong>
    </p>
    <p class="auth-confirm-sub">Click the link in the email to activate your account.</p>
    <button class="provider-btn" onclick="closeAuthModal()">Got it</button>
  `;
}

function toggleAuthMode(e) {
  e.preventDefault();
  _authMode = _authMode === "signin" ? "signup" : "signin";
  const isSignup = _authMode === "signup";
  document.getElementById("auth-submit").textContent     = isSignup ? "Sign up" : "Sign in";
  document.getElementById("auth-toggle-text").textContent = isSignup ? "Already have an account?" : "Don't have an account?";
  document.getElementById("auth-toggle-link").textContent = isSignup ? "Sign in" : "Sign up";
  document.getElementById("auth-error").hidden = true;
}

/* ── social ──────────────────────────────────────────────── */
async function signInWith(provider) {
  const sb = await getSupabase();
  if (!sb) return;
  const appRoot = window.location.origin +
    window.location.pathname.replace(/\/$/, "").replace(/\/cookbook$/, "") + "/";
  await sb.auth.signInWithOAuth({
    provider,
    options: { redirectTo: appRoot },
  });
}

/* ── email / password ─────────────────────────────────────── */
async function handleEmailAuth(e) {
  e.preventDefault();
  const sb = await getSupabase();
  if (!sb) return;

  const email    = document.getElementById("auth-email").value.trim();
  const password = document.getElementById("auth-password").value;
  const errEl    = document.getElementById("auth-error");
  const btn      = document.getElementById("auth-submit");

  btn.disabled = true;
  errEl.hidden = true;

  const { error } =
    _authMode === "signup"
      ? await sb.auth.signUp({ email, password })
      : await sb.auth.signInWithPassword({ email, password });

  btn.disabled = false;

  if (error) {
    errEl.textContent = error.message;
    errEl.hidden = false;
  } else if (_authMode === "signup") {
    _showConfirmation(email);
  }
}

/* ── sign out ─────────────────────────────────────────────── */
async function signOut() {
  const sb = await getSupabase();
  if (!sb) return;
  await sb.auth.signOut();
}
