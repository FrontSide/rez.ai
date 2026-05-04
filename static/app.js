/* ── base path (works behind a subpath reverse proxy) ──────── */
const _base = (() => {
  const p = window.location.pathname.replace(/\/$/, "");
  if (p.endsWith("/cookbook")) return p.slice(0, -"/cookbook".length);
  return p;
})();

/* ── state ─────────────────────────────────────────────────── */
let currentQuery = "";
let _savedUrls   = new Set(); // urls saved by the current user

/* ── elements ──────────────────────────────────────────────── */
const resultsSection  = document.getElementById("results-section");
const resultsHeading  = document.getElementById("results-heading");
const resultsGrid     = document.getElementById("results-grid");
const recipeSection   = document.getElementById("recipe-section");
const cookbookSection = document.getElementById("cookbook-section");
const cookbookGrid    = document.getElementById("cookbook-grid");
const searchInput     = document.getElementById("search-input");
const toast           = document.getElementById("toast");

/* ── routing ───────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("logo").href          = _base + "/";
  document.getElementById("nav-explore").href   = _base + "/";
  document.getElementById("nav-cookbook").href  = _base + "/cookbook";
  routeFromURL();
});
window.addEventListener("popstate", () => routeFromURL());

function routeFromURL() {
  const params = new URLSearchParams(window.location.search);
  const path   = window.location.pathname.replace(/\/$/, "");
  const recipe = params.get("recipe");
  const q      = params.get("q");

  if (recipe) {
    loadRecipe(recipe, false);
  } else if (q) {
    searchInput.value = q;
    showResults(q, false);
  } else if (path === _base + "/cookbook") {
    showCookbook(false);
  } else {
    loadFeatured(false);
  }
}

function navigate(section) {
  if (section === "cookbook") {
    history.pushState({}, "", _base + "/cookbook");
    showCookbook(false);
  } else {
    history.pushState({}, "", _base + "/");
    loadFeatured(false);
  }
}

function _setActiveNav(section) {
  document.getElementById("nav-explore").classList.toggle("active", section === "explore");
  document.getElementById("nav-cookbook").classList.toggle("active", section === "cookbook");
}

function _hideAll() {
  resultsSection.hidden  = true;
  recipeSection.hidden   = true;
  cookbookSection.hidden = true;
}

/* ── saved state ───────────────────────────────────────────── */
async function _loadSavedUrls() {
  const sb = await getSupabase();
  if (!sb) return;
  const { data: { session } } = await sb.auth.getSession();
  if (!session) return;

  try {
    const res = await fetch("api/saves", {
      headers: { Authorization: `Bearer ${session.access_token}` },
    });
    if (!res.ok) return;
    const data = await res.json();
    _savedUrls = new Set(data.results.map(r => r.url));
  } catch { /* silently ignore */ }
}

async function toggleSave(url, btn) {
  const sb = await getSupabase();
  if (!sb) { openAuthModal(); return; }
  const { data: { session } } = await sb.auth.getSession();
  if (!session) { openAuthModal(); return; }

  const isSaved = _savedUrls.has(url);
  const method  = isSaved ? "DELETE" : "POST";

  try {
    const res = await fetch(`api/saves?url=${encodeURIComponent(url)}`, {
      method,
      headers: { Authorization: `Bearer ${session.access_token}` },
    });
    if (res.status === 401) { openAuthModal(); return; }
    if (!res.ok) throw new Error();
    if (isSaved) {
      _savedUrls.delete(url);
    } else {
      _savedUrls.add(url);
    }
    _updateBookmarkBtn(btn, !isSaved);
    showToast(isSaved ? "Removed from cookbook" : "Saved to cookbook");
  } catch {
    showToast("Could not update cookbook");
  }
}

function _updateBookmarkBtn(btn, saved) {
  if (!btn) return;
  btn.classList.toggle("saved", saved);
  btn.title = saved ? "Remove from cookbook" : "Save to cookbook";
  btn.textContent = saved ? "★" : "☆";
}

/* ── startup / featured ────────────────────────────────────── */
async function loadFeatured(push = true) {
  if (push) history.pushState({}, "", _base + "/");
  _setActiveNav("explore");
  currentQuery = "";
  searchInput.value = "";
  _hideAll();
  resultsSection.hidden = false;
  resultsHeading.innerHTML = "Popular recipes";
  renderSkeletons(resultsGrid);
  await _loadSavedUrls();

  try {
    const res = await fetch("api/featured");
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderCards(resultsGrid, data.results);
  } catch (err) {
    resultsGrid.innerHTML = `<p class="error">Could not load featured recipes: ${escHtml(String(err))}</p>`;
  }
}

/* ── search ────────────────────────────────────────────────── */
async function handleSearch(e) {
  e.preventDefault();
  const q = searchInput.value.trim();
  if (!q) return;
  showResults(q, true);
}

async function showResults(q, push = true) {
  if (push) history.pushState({}, "", `${_base}/?q=${encodeURIComponent(q)}`);
  _setActiveNav("explore");
  currentQuery = q;
  searchInput.value = q;
  _hideAll();
  resultsSection.hidden = false;
  resultsHeading.innerHTML = `Results for <span>"${escHtml(q)}"</span>`;
  renderSkeletons(resultsGrid);
  await _loadSavedUrls();

  try {
    const res = await fetch(`api/search?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderCards(resultsGrid, data.results);
  } catch (err) {
    resultsGrid.innerHTML = `<p class="error">Search failed: ${escHtml(String(err))}</p>`;
  }
}

/* ── cookbook ──────────────────────────────────────────────── */
async function showCookbook(push = true) {
  if (push) history.pushState({}, "", _base + "/cookbook");
  _setActiveNav("cookbook");
  _hideAll();
  cookbookSection.hidden = false;

  const sb = await getSupabase();
  if (!sb) { _showCookbookAuthPrompt(); return; }
  const { data: { session } } = await sb.auth.getSession();
  if (!session) { _showCookbookAuthPrompt(); return; }

  renderSkeletons(cookbookGrid);
  await _loadSavedUrls();

  try {
    const res = await fetch("api/saves", {
      headers: { Authorization: `Bearer ${session.access_token}` },
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    if (!data.results.length) {
      cookbookGrid.innerHTML = `<p class="cookbook-empty">No saved recipes yet — explore and click ☆ to add some.</p>`;
    } else {
      renderCards(cookbookGrid, data.results);
    }
  } catch (err) {
    cookbookGrid.innerHTML = `<p class="error">Could not load cookbook: ${escHtml(String(err))}</p>`;
  }
}

function _showCookbookAuthPrompt() {
  cookbookGrid.innerHTML = `
    <div class="cookbook-auth-prompt">
      <p>Sign in to save recipes and build your personal cookbook.</p>
      <button class="provider-btn" style="max-width:240px" onclick="openAuthModal()">Sign in</button>
    </div>
  `;
}

/* ── cards ─────────────────────────────────────────────────── */
function renderSkeletons(grid) {
  grid.innerHTML = Array.from({ length: 8 }, () => `
    <div class="skeleton-card">
      <div class="skeleton skeleton-img"></div>
      <div class="skeleton-body">
        <div class="skeleton skeleton-line short"></div>
        <div class="skeleton skeleton-line"></div>
        <div class="skeleton skeleton-line"></div>
        <div class="skeleton skeleton-line short"></div>
      </div>
    </div>
  `).join("");
}

function renderCards(grid, results) {
  if (!results.length) {
    grid.innerHTML = `<p style="color:var(--muted)">No recipes found. Try a different search.</p>`;
    return;
  }
  grid.innerHTML = results.map(r => {
    const saved = _savedUrls.has(r.url);
    return `
      <a class="recipe-card" href="#" data-recipe-url="${escHtml(r.url)}">
        ${r.image_url
          ? `<img src="${escHtml(r.image_url)}" alt="${escHtml(r.title)}" loading="lazy" />`
          : `<div class="card-img-placeholder">🍽️</div>`
        }
        <div class="card-body">
          <span class="card-source">${sourceLabel(r.source)}</span>
          <span class="card-title">${escHtml(r.title)}</span>
          ${r.cook_time ? `<span class="card-meta">⏱ ${escHtml(r.cook_time)}</span>` : ""}
        </div>
        <button class="bookmark-btn${saved ? " saved" : ""}"
          title="${saved ? "Remove from cookbook" : "Save to cookbook"}"
          data-bookmark-url="${escHtml(r.url)}"
          onclick="event.preventDefault(); event.stopPropagation(); toggleSave(this.dataset.bookmarkUrl, this)">
          ${saved ? "★" : "☆"}
        </button>
      </a>
    `;
  }).join("");
}

resultsGrid.addEventListener("click", e => {
  const card = e.target.closest("[data-recipe-url]");
  if (!card || e.target.closest(".bookmark-btn")) return;
  e.preventDefault();
  loadRecipe(card.dataset.recipeUrl, true);
});

cookbookGrid.addEventListener("click", e => {
  const card = e.target.closest("[data-recipe-url]");
  if (!card || e.target.closest(".bookmark-btn")) return;
  e.preventDefault();
  loadRecipe(card.dataset.recipeUrl, true);
});

/* ── recipe detail ─────────────────────────────────────────── */
async function loadRecipe(url, push = true) {
  if (push) history.pushState({}, "", `${_base}/?recipe=${encodeURIComponent(url)}`);
  _hideAll();
  recipeSection.hidden = false;
  recipeSection.innerHTML = renderRecipeSkeleton();
  await _loadSavedUrls();

  try {
    const res = await fetch(`api/recipe?url=${encodeURIComponent(url)}`);
    if (!res.ok) throw new Error(await res.text());
    const recipe = await res.json();
    renderRecipe(recipe);
  } catch (err) {
    recipeSection.innerHTML = `
      <button class="recipe-back" onclick="history.back()">← Back</button>
      <p class="error">Failed to load recipe: ${escHtml(String(err))}</p>
    `;
  }
}

function renderRecipe(r) {
  const meta = r.metadata || {};
  const saved = _savedUrls.has(r.url);

  const metaItems = [
    { label: "Prep",     value: meta.prep_time },
    { label: "Cook",     value: meta.cook_time },
    { label: "Total",    value: meta.total_time },
    { label: "Servings", value: Array.isArray(meta.servings) ? meta.servings[0] : meta.servings },
    { label: "Cuisine",  value: meta.cuisine },
    { label: "Rating",   value: meta.rating ? `${Number(meta.rating).toFixed(1)} ★ (${meta.rating_count})` : null },
  ].filter(m => m.value);

  const metaBar = metaItems.length ? `
    <div class="recipe-meta-bar">
      ${metaItems.map(m => `
        <div class="meta-item">
          <span class="meta-label">${escHtml(m.label)}</span>
          <span class="meta-value">${escHtml(String(m.value))}</span>
        </div>
      `).join("")}
    </div>
  ` : "";

  const ingredients = (r.ingredients || []).map(i => `<li>${escHtml(i)}</li>`).join("");
  const steps = (r.method || []).map((step, i) => `
    <li class="method-step">
      <span class="step-number">${i + 1}</span>
      <span class="step-text">${escHtml(step)}</span>
    </li>
  `).join("");

  recipeSection.innerHTML = `
    <div class="recipe-topbar">
      <button class="recipe-back" onclick="history.back()">← Back to results</button>
      <button class="recipe-save-btn${saved ? " saved" : ""}"
        title="${saved ? "Remove from cookbook" : "Save to cookbook"}"
        data-bookmark-url="${escHtml(r.url)}"
        onclick="toggleSave(this.dataset.bookmarkUrl, this)">
        ${saved ? "★ Saved" : "☆ Save to Cookbook"}
      </button>
    </div>

    <div class="recipe-layout">
      ${r.image_url ? `<img class="recipe-side-img" src="${escHtml(r.image_url)}" alt="${escHtml(r.title)}" />` : ""}
      <div class="recipe-content">
        <a class="recipe-source-badge" href="${escHtml(r.url)}" target="_blank" rel="noopener noreferrer">Recipe from: ${sourceLabel(r.source)} ↗</a>
        <h1 class="recipe-title">${escHtml(r.title)}</h1>
        ${r.description ? `<p class="recipe-description">${escHtml(r.description)}</p>` : ""}
        ${metaBar}
        <div class="recipe-columns">
          <div>
            <span class="recipe-section-title">Ingredients</span>
            <ul class="ingredients-list">${ingredients || "<li>No ingredients found.</li>"}</ul>
          </div>
          <div>
            <span class="recipe-section-title">Method</span>
            <ol class="method-list">${steps || "<li>No method found.</li>"}</ol>
          </div>
        </div>
      </div>
    </div>
  `;

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderRecipeSkeleton() {
  return `
    <div class="skeleton skeleton-img" style="width:100%;max-height:420px;margin-bottom:1.75rem;aspect-ratio:16/7"></div>
    <div class="skeleton skeleton-line short" style="height:1.5rem;margin-bottom:.5rem"></div>
    <div class="skeleton skeleton-line" style="height:2.5rem;margin-bottom:1rem"></div>
    <div class="skeleton skeleton-line" style="height:1rem;margin-bottom:.5rem"></div>
    <div class="skeleton skeleton-line short" style="height:1rem;margin-bottom:2rem"></div>
  `;
}

/* ── utils ─────────────────────────────────────────────────── */
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function sourceLabel(source) {
  const labels = { bbc_good_food: "BBC Good Food" };
  return labels[source] || source;
}

function showToast(msg) {
  toast.textContent = msg;
  toast.hidden = false;
  setTimeout(() => { toast.hidden = true; }, 2500);
}
