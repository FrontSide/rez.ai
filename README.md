# rez.ai

A recipe search and reader that scrapes well-known recipe sites, extracts ingredients and method, and caches everything locally. Every recipe is displayed in the same clean format regardless of where it came from.

## How it works

1. User searches for a recipe — cached results are returned immediately from Elasticsearch, while live scraper results stream in progressively via SSE.
2. User clicks a result — if the recipe has been fully scraped before it's served instantly from SQLite; otherwise it's scraped on the fly, cached, and indexed into ES.
3. Every recipe is shown in the same layout: image, metadata (prep/cook time, servings), ingredients list, numbered method steps.

## Stack

| Layer | Tech |
|---|---|
| Backend | [FastAPI](https://fastapi.tiangolo.com/) |
| Recipe cache | SQLite via [SQLAlchemy](https://www.sqlalchemy.org/) |
| Search index | [Elasticsearch](https://www.elastic.co/elasticsearch) 8.x (fuzzy full-text, SSE streaming) |
| Scraping | [httpx](https://www.python-httpx.org/) + [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) |
| Auth | Self-hosted: Google OAuth via [httpx-oauth](https://frankie567.github.io/httpx-oauth/), email/password with bcrypt, HS256 JWTs |
| Frontend | Vanilla JS, no build step |

## Getting started

Copy `.env.example` to `.env` and fill in your credentials (see [Configuration](#configuration)):

```bash
cp .env.example .env
# edit .env
```

Start Elasticsearch (required) and the app:

```bash
docker compose up elasticsearch -d
pip install -r requirements.txt
export $(cat .env | xargs)
uvicorn main:app --reload
```

Then open [http://localhost:8000](http://localhost:8000).

## Configuration

Create a `.env` file (never commit this):

```env
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
GOOGLE_CLIENT_ID=<your-google-oauth-client-id>
GOOGLE_CLIENT_SECRET=<your-google-oauth-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/callback
```

### Google OAuth setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → **APIs & Services → Credentials**.
2. Create an **OAuth 2.0 Client ID** (type: Web application).
3. Add your redirect URI(s) under **Authorised redirect URIs**:
   - `http://localhost:8000/api/auth/callback` for local dev
   - `http://192.168.178.162:8090/api/auth/callback` (or your production URL) for the homelab
4. Copy the Client ID and Client Secret into `.env`.

### How auth works

The backend handles the full OAuth flow directly — no third-party auth service involved. On Google login, the user is redirected to `/api/auth/google`, which bounces them to Google and handles the callback at `/api/auth/callback`. On success, the backend creates or finds the user in the local database and issues a signed HS256 JWT. Email/password accounts are also supported — passwords are hashed with bcrypt and stored in the local `users` table. All protected routes verify the JWT using the `SECRET_KEY`.

## Deployment

Merging a PR into `main` automatically triggers a deployment via GitHub Actions (`.github/workflows/deploy.yml`). The workflow runs on a self-hosted runner installed on the production server, pulls the latest code, and rebuilds the Docker container.

**Flow:**
1. Open a PR from a feature branch
2. Review and merge into `main`
3. GitHub Actions runs on the self-hosted runner → `git pull` + `docker compose up -d --build`
4. Confirm the new version number in the bottom-left corner of the app

**Manual deploy** (if needed):
```bash
ssh david@192.168.178.162 "cd ~/rez.ai && git pull && docker compose up -d --build"
```

The compose file expects `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI` to be present in a `.env` file in the project directory on the server. Recipe data and the Elasticsearch index are persisted to `/home/david/data/rez.ai` on the host.

**After first deploy** (or to backfill existing cached recipes into ES):
```bash
docker compose exec rez-ai python reindex.py
```

## API

| Endpoint | Description |
|---|---|
| `GET /api/featured` | Returns a curated mix of popular recipes |
| `GET /api/search?q=<query>` | SSE stream: cached ES results first, then live scraper results |
| `GET /api/recipe?url=<url>` | Fetch a recipe (from cache or scraped live) |
| `GET /api/config` | Returns app version |
| `GET /api/auth/google` | Initiates Google OAuth flow |
| `GET /api/auth/callback` | Google OAuth callback — issues JWT and redirects to app |
| `POST /api/auth/login` | Email/password login — returns JWT |
| `POST /api/auth/signup` | Email/password sign-up — returns JWT |

## Adding more recipe sources

Create a new file under `scraper/` that exposes two functions:

```python
def search(query: str) -> list[dict]: ...
def scrape_recipe(url: str) -> dict: ...
```

The returned dict from `scrape_recipe` should have the keys: `url`, `source`, `title`, `description`, `image_url`, `ingredients` (list of strings), `method` (list of strings), `metadata` (dict).

Then wire it into the relevant routes in `main.py`.

## Supported sources

- [BBC Good Food](https://www.bbcgoodfood.com) (English)
- [Gutekueche.at](https://www.gutekueche.at) (German)
