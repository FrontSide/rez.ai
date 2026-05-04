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
| Auth | [Supabase Auth](https://supabase.com/auth) (JWT verification via JWKS, RS256) |
| Frontend | Vanilla JS, no build step |

## Getting started

Copy `.env.example` to `.env` and fill in your Supabase credentials (see [Configuration](#configuration)):

```bash
cp .env.example .env
# edit .env
```

Install dependencies and run:

```bash
pip install -r requirements.txt
export $(cat .env | xargs)
uvicorn main:app --reload
```

Then open [http://localhost:8000](http://localhost:8000).

## Configuration

Create a `.env` file (never commit this):

```env
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_ANON_KEY=<your-anon-key>
```

Both values are found in your Supabase project under **Settings → API**.

### Supabase setup

1. Create a project at [supabase.com](https://supabase.com).
2. Enable **Authentication → Providers → Google** (and any others you want). Each provider requires a Client ID and Secret from that provider's developer console.
3. Add your app's URL to **Authentication → URL Configuration → Redirect URLs** (e.g. `http://localhost:8000` for local dev).
4. Optionally customise the confirmation email under **Authentication → Email Templates**.

### How auth works

The backend never stores passwords or talks to Supabase at request time. Supabase issues RS256-signed JWTs; the backend verifies them locally using Supabase's public JWKS endpoint (fetched once and cached). No shared secret is required.

## Deployment

```bash
docker compose up -d
```

The compose file expects `SUPABASE_URL` and `SUPABASE_ANON_KEY` to be present in the environment (or a `.env` file in the same directory). Recipe data is persisted to `/home/david/data/rez.ai` on the host.

## API

| Endpoint | Description |
|---|---|
| `GET /api/featured` | Returns a curated mix of popular recipes |
| `GET /api/search?q=<query>` | Search BBC Good Food, returns up to 30 results |
| `GET /api/recipe?url=<url>` | Fetch a recipe (from cache or scraped live) |
| `GET /api/config` | Returns public Supabase credentials for the frontend |

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
