/* ── state ─────────────────────────────────────────────────── */
let currentQuery = "";

/* ── elements ──────────────────────────────────────────────── */
const resultsSection = document.getElementById("results-section");
const resultsHeading = document.getElementById("results-heading");
const resultsGrid    = document.getElementById("results-grid");
const recipeSection  = document.getElementById("recipe-section");
const searchInput    = document.getElementById("search-input");
const toast          = document.getElementById("toast");

/* ── startup ───────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", loadFeatured);

async function loadFeatured() {
  currentQuery = "";
  searchInput.value = "";
  recipeSection.hidden = true;
  resultsSection.hidden = false;
  resultsHeading.innerHTML = "Popular recipes";
  renderSkeletons();

  try {
    const res = await fetch("api/featured");
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderCards(data.results);
  } catch (err) {
    resultsGrid.innerHTML = `<p class="error">Could not load featured recipes: ${escHtml(String(err))}</p>`;
  }
}

/* ── search ────────────────────────────────────────────────── */
async function handleSearch(e) {
  e.preventDefault();
  const q = searchInput.value.trim();
  if (!q) return;
  currentQuery = q;
  showResults(q);
}

async function showResults(q) {
  recipeSection.hidden = true;
  resultsSection.hidden = false;
  resultsHeading.innerHTML = `Results for <span>"${escHtml(q)}"</span>`;
  renderSkeletons();

  try {
    const res = await fetch(`api/search?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderCards(data.results);
  } catch (err) {
    resultsGrid.innerHTML = `<p class="error">Search failed: ${escHtml(String(err))}</p>`;
  }
}

function renderSkeletons() {
  resultsGrid.innerHTML = Array.from({ length: 8 }, () => `
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

function renderCards(results) {
  if (!results.length) {
    resultsGrid.innerHTML = `<p style="color:var(--muted)">No recipes found. Try a different search.</p>`;
    return;
  }
  resultsGrid.innerHTML = results.map(r => `
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
    </a>
  `).join("");
}

resultsGrid.addEventListener("click", e => {
  const card = e.target.closest("[data-recipe-url]");
  if (!card) return;
  e.preventDefault();
  loadRecipe(card.dataset.recipeUrl);
});

/* ── recipe detail ─────────────────────────────────────────── */
async function loadRecipe(url) {
  resultsSection.hidden = true;
  recipeSection.hidden = false;
  recipeSection.innerHTML = renderRecipeSkeleton();

  try {
    const res = await fetch(`api/recipe?url=${encodeURIComponent(url)}`);
    if (!res.ok) throw new Error(await res.text());
    const recipe = await res.json();
    renderRecipe(recipe);
  } catch (err) {
    recipeSection.innerHTML = `
      <button class="recipe-back" onclick="goBack()">← Back</button>
      <p class="error">Failed to load recipe: ${escHtml(String(err))}</p>
    `;
  }
}

function renderRecipe(r) {
  const meta = r.metadata || {};

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

  const ingredients = (r.ingredients || []).map(i => `
    <li>${escHtml(i)}</li>
  `).join("");

  const steps = (r.method || []).map((step, i) => `
    <li class="method-step">
      <span class="step-number">${i + 1}</span>
      <span class="step-text">${escHtml(step)}</span>
    </li>
  `).join("");

  recipeSection.innerHTML = `
    <button class="recipe-back" onclick="goBack()">← Back to results</button>

    <div class="recipe-layout">
      ${r.image_url ? `<img class="recipe-side-img" src="${escHtml(r.image_url)}" alt="${escHtml(r.title)}" />` : ""}
      <div class="recipe-content">
        <span class="recipe-source-badge">${sourceLabel(r.source)}</span>
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

/* ── navigation ────────────────────────────────────────────── */
function goBack() {
  recipeSection.hidden = true;
  resultsSection.hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
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
  const labels = {
    bbc_good_food: "BBC Good Food",
  };
  return labels[source] || source;
}

function showToast(msg) {
  toast.textContent = msg;
  toast.hidden = false;
  setTimeout(() => { toast.hidden = true; }, 2500);
}
