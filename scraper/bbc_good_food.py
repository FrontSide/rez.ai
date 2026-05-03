"""
BBC Good Food scraper.

Search results live in a server-rendered application/json script tag
(script index 5 on the search page) under data['searchResults']['items'].

Individual recipe pages carry a JSON-LD block with @type="Recipe".
"""
import json
import re
from typing import Optional
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.bbcgoodfood.com"
SEARCH_URL = f"{BASE_URL}/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


def _client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20)


# ── public API ──────────────────────────────────────────────────────────────

def search(query: str) -> list[dict]:
    url = f"{SEARCH_URL}?{urlencode({'q': query})}"
    with _client() as client:
        resp = client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Results are embedded in a server-side JSON block (script[5] by convention,
    # but we identify it by the presence of the 'searchResults' key).
    for script in soup.find_all("script", type="application/json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, AttributeError):
            continue
        if "searchResults" not in data:
            continue

        items = data["searchResults"].get("items", [])
        return [_normalise_search_item(item) for item in items if item.get("postType") == "recipe"]

    return []


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

def _normalise_search_item(item: dict) -> dict:
    image = item.get("image") or {}
    terms = item.get("terms") or []
    time_term = next((t["display"] for t in terms if t.get("slug") == "time"), None)
    rating = item.get("rating") or {}

    # Strip HTML tags from description
    raw_desc = item.get("description", "") or ""
    description = BeautifulSoup(raw_desc, "html.parser").get_text(strip=True)

    return {
        "url": item["url"],
        "title": item.get("title", ""),
        "image_url": image.get("url"),
        "description": description,
        "cook_time": time_term,
        "rating": rating.get("ratingValue"),
        "rating_count": rating.get("ratingCount"),
        "source": "bbc_good_food",
    }


def _find_recipe_node(data) -> Optional[dict]:
    if isinstance(data, list):
        for item in data:
            found = _find_recipe_node(item)
            if found:
                return found
    if isinstance(data, dict):
        if data.get("@type") == "Recipe":
            return data
        for node in data.get("@graph", []):
            if isinstance(node, dict) and node.get("@type") == "Recipe":
                return node
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
            text = step.strip()
        elif isinstance(step, dict):
            text = step.get("text", "").strip()
        else:
            continue
        if text:
            method.append(text)

    rating = data.get("aggregateRating") or {}

    return {
        "url": url,
        "source": "bbc_good_food",
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
            "rating_count": rating.get("ratingCount") if isinstance(rating, dict) else None,
        },
    }


def _parse_html_fallback(soup: BeautifulSoup, url: str) -> dict:
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)

    ingredients = []
    for li in soup.find_all("li", class_=re.compile(r"ingredient", re.I)):
        text = li.get_text(" ", strip=True)
        if text:
            ingredients.append(text)

    method = []
    for elem in soup.find_all(class_=re.compile(r"(method|step|instruction)", re.I)):
        text = elem.get_text(" ", strip=True)
        if len(text) > 15 and text not in method:
            method.append(text)

    image = None
    og = soup.find("meta", property="og:image")
    if og:
        image = og.get("content")

    return {
        "url": url,
        "source": "bbc_good_food",
        "title": title,
        "description": "",
        "image_url": image,
        "ingredients": ingredients,
        "method": method,
        "metadata": {},
    }
