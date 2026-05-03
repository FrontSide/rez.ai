# rez.ai

A recipe search and reader that scrapes well-known recipe sites, extracts ingredients and method, and caches everything in a local database. Every recipe is displayed in the same clean format regardless of where it came from.

## How it works

1. User searches for a recipe — results are fetched live from BBC Good Food's search.
2. User clicks a result — if the recipe has been seen before it's served instantly from the cache; otherwise it's scraped on the fly, cached, and returned.
3. Every recipe is shown in the same layout: image, metadata (prep/cook time, servings), ingredients list, numbered method steps.

## Stack

| Layer | Tech |
|---|---|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) |
| Database | SQLite via [SQLAlchemy](https://www.sqlalchemy.org/) |
| Scraping | [httpx](https://www.python-httpx.org/) + [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) |
| Frontend | Vanilla JS, no build step |

## Getting started

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open [http://localhost:8000](http://localhost:8000).

## API

| Endpoint | Description |
|---|---|
| `GET /api/search?q=<query>` | Search BBC Good Food, returns up to 30 results |
| `GET /api/recipe?url=<url>` | Fetch a recipe (from cache or scraped live) |

## Adding more recipe sources

Create a new file under `scraper/` that exposes two functions:

```python
def search(query: str) -> list[dict]: ...
def scrape_recipe(url: str) -> dict: ...
```

The returned dict from `scrape_recipe` should have the keys: `url`, `source`, `title`, `description`, `image_url`, `ingredients` (list of strings), `method` (list of strings), `metadata` (dict).

Then wire it into the relevant routes in `main.py`.

## Supported sources

- [BBC Good Food](https://www.bbcgoodfood.com)
