"""
Gutekueche.at scraper (German-language recipes).

Search results are server-rendered HTML; each result card has an <h3> with
a link matching /{slug}-rezept-{id}.

Individual recipe pages carry a JSON-LD array where one entry has @type="Recipe".
"""
import json
import re
from typing import Optional
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.gutekueche.at"
SEARCH_URL = f"{BASE_URL}/suche"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-AT,de;q=0.9",
}

_RECIPE_PATH_RE = re.compile(r"^/[^/]+-rezept-\d+$")


def _client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20)


# ── public API ──────────────────────────────────────────────────────────────

def search(query: str) -> list[dict]:
    url = f"{SEARCH_URL}?{urlencode({'s': query})}"
    with _client() as client:
        resp = client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for h3 in soup.find_all("h3"):
        a = h3.find("a", href=_RECIPE_PATH_RE)
        if not a:
            continue

        title = a.get_text(strip=True)
        recipe_url = BASE_URL + a["href"]

        # Image lives in a sibling/ancestor div - walk up to the row container
        image_url = None
        row = h3.find_parent("div", class_=re.compile(r"col"))
        if row:
            container = row.find_parent("div") or row
            img = container.find("img")
            if img and img.get("src"):
                image_url = img["src"]

        # Rating: <div class="starrating" title="4.61 von 5 Punkten">
        rating = None
        star_div = h3.find_next("div", class_="starrating")
        if star_div:
            title_attr = star_div.get("title", "")
            m = re.search(r"([\d,.]+)\s+von\s+5", title_attr)
            if m:
                rating = float(m.group(1).replace(",", "."))

        results.append({
            "url": recipe_url,
            "title": title,
            "image_url": image_url,
            "description": "",
            "cook_time": None,
            "rating": rating,
            "rating_count": None,
            "source": "gutekueche_at",
        })

    return results


def scrape_recipe(url: str) -> dict:
    with _client() as client:
        resp = client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, AttributeError):
            continue
        recipe_node = _find_recipe_node(data)
        if recipe_node:
            return _parse_json_ld(recipe_node, url)

    return _parse_html_fallback(soup, url)


# ── internals ───────────────────────────────────────────────────────────────

def _find_recipe_node(data) -> Optional[dict]:
    if isinstance(data, list):
        for item in data:
            found = _find_recipe_node(item)
            if found:
                return found
    if isinstance(data, dict):
        if data.get("@type") == "Recipe":
            return data
    return None


def _parse_duration(iso: Optional[str]) -> Optional[str]:
    if not iso:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", iso)
    if not m:
        return iso
    parts = []
    if m.group(1):
        parts.append(f"{m.group(1)} hr")
    if m.group(2):
        parts.append(f"{m.group(2)} min")
    return " ".join(parts) if parts else None


def _extract_image_url(image_field) -> Optional[str]:
    if isinstance(image_field, list):
        image_field = image_field[0] if image_field else None
    if isinstance(image_field, dict):
        return image_field.get("url")
    return image_field


def _parse_json_ld(data: dict, url: str) -> dict:
    ingredients = data.get("recipeIngredient", [])

    method = []
    for step in data.get("recipeInstructions", []):
        if isinstance(step, str):
            # Strip leading "N. " numbering added by the site
            text = re.sub(r"^\d+\.\s*", "", step.strip())
        elif isinstance(step, dict):
            text = re.sub(r"^\d+\.\s*", "", step.get("text", "").strip())
        else:
            continue
        if text:
            method.append(text)

    rating = data.get("aggregateRating") or {}

    return {
        "url": url,
        "source": "gutekueche_at",
        "title": data.get("name", ""),
        "description": data.get("description", ""),
        "image_url": _extract_image_url(data.get("image")),
        "ingredients": ingredients,
        "method": method,
        "metadata": {
            "prep_time": _parse_duration(data.get("prepTime")),
            "cook_time": _parse_duration(data.get("cookTime")),
            "total_time": _parse_duration(data.get("totalTime")),
            "servings": data.get("recipeYield"),
            "cuisine": data.get("recipeCuisine"),
            "category": data.get("recipeCategory"),
            "keywords": data.get("keywords"),
            "rating": rating.get("ratingValue") if isinstance(rating, dict) else None,
            "rating_count": rating.get("reviewCount") if isinstance(rating, dict) else None,
        },
    }


def _parse_html_fallback(soup: BeautifulSoup, url: str) -> dict:
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)

    ingredients = []
    table = soup.find("div", class_="ingredients-table")
    if table:
        for row in table.find_all("tr"):
            text = row.get_text(" ", strip=True)
            if text:
                ingredients.append(text)

    method = []
    prep_section = soup.find("section", class_="rezept-preperation")
    if prep_section:
        for li in prep_section.find_all("li"):
            text = li.get_text(strip=True)
            if text:
                method.append(text)

    image = None
    og = soup.find("meta", property="og:image")
    if og:
        image = og.get("content")

    return {
        "url": url,
        "source": "gutekueche_at",
        "title": title,
        "description": "",
        "image_url": image,
        "ingredients": ingredients,
        "method": method,
        "metadata": {},
    }
