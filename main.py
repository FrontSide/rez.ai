import asyncio
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from urllib.parse import unquote

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from httpx_oauth.clients.google import GoogleOAuth2
from pydantic import BaseModel

from auth import create_token, hash_password, require_user, verify_password
from database import Recipe, SavedRecipe, SessionLocal, User, init_db
from scraper import bbc_good_food, gutekueche_at
import search as es

_GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
_GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
_GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/callback")
_APP_BASE             = _GOOGLE_REDIRECT_URI.removesuffix("/api/auth/callback")

_google = GoogleOAuth2(_GOOGLE_CLIENT_ID, _GOOGLE_CLIENT_SECRET)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await es.ensure_index()
    yield


app = FastAPI(title="rez.ai", lifespan=lifespan)


# --- API routes (must be registered before static mount) ---

_FEATURED_QUERIES_BBC = ["pasta", "chicken", "chocolate cake", "salad"]
_FEATURED_QUERIES_GK  = ["Auflauf", "Suppe", "Kuchen", "Salat"]

@app.get("/api/featured")
async def featured_recipes():
    tasks = (
        [asyncio.to_thread(bbc_good_food.search, q) for q in _FEATURED_QUERIES_BBC]
        + [asyncio.to_thread(gutekueche_at.search, q) for q in _FEATURED_QUERIES_GK]
    )
    results_lists = await asyncio.gather(*tasks, return_exceptions=True)

    seen: set[str] = set()
    combined: list[dict] = []
    max_len = max((len(r) for r in results_lists if isinstance(r, list)), default=0)
    for i in range(max_len):
        for r in results_lists:
            if isinstance(r, list) and i < len(r) and r[i]["url"] not in seen:
                seen.add(r[i]["url"])
                combined.append(r[i])

    return {"results": combined[:16]}


@app.get("/api/search")
async def search_recipes(q: str = Query(..., min_length=1)):
    async def _stream():
        # 1. Cached results from ES — returned immediately
        cached = await es.search(q)
        if cached:
            yield f"data: {json.dumps({'results': cached})}\n\n"

        # 2. Live scraper results — push anything not already in ES
        seen = {r["url"] for r in cached}
        bbc_task = asyncio.to_thread(bbc_good_food.search, q)
        gk_task  = asyncio.to_thread(gutekueche_at.search, q)
        bbc_res, gk_res = await asyncio.gather(bbc_task, gk_task, return_exceptions=True)

        fresh: list[dict] = []
        for result_list in (bbc_res, gk_res):
            if isinstance(result_list, Exception):
                continue
            for r in result_list:
                if r["url"] not in seen:
                    fresh.append(r)
                    seen.add(r["url"])

        if fresh:
            yield f"data: {json.dumps({'results': fresh})}\n\n"

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/recipe")
async def get_recipe(url: str = Query(...)):
    url = unquote(url)

    with SessionLocal() as session:
        cached = session.query(Recipe).filter(Recipe.url == url).first()
        if cached:
            return _to_dict(cached, from_cache=True)

    scraper = gutekueche_at if "gutekueche.at" in url else bbc_good_food
    try:
        data = await asyncio.to_thread(scraper.scrape_recipe, url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scrape failed: {e}")

    with SessionLocal() as session:
        recipe = Recipe(
            url=data["url"],
            source=data["source"],
            title=data["title"],
            description=data.get("description", ""),
            image_url=data.get("image_url"),
            ingredients=data.get("ingredients", []),
            method=data.get("method", []),
            metadata_=data.get("metadata", {}),
        )
        session.add(recipe)
        session.commit()
        session.refresh(recipe)
        await es.index_recipe(data)
        return _to_dict(recipe, from_cache=False)


@app.get("/api/saves")
async def list_saves(user: dict = Depends(require_user)):
    user_id = user["sub"]
    with SessionLocal() as session:
        rows = (
            session.query(SavedRecipe, Recipe)
            .join(Recipe, Recipe.url == SavedRecipe.recipe_url)
            .filter(SavedRecipe.user_id == user_id)
            .order_by(SavedRecipe.saved_at.desc())
            .all()
        )
    return {"results": [_to_dict(recipe, from_cache=True) for _, recipe in rows]}


@app.post("/api/saves")
async def save_recipe(url: str = Query(...), user: dict = Depends(require_user)):
    url = unquote(url)
    user_id = user["sub"]
    with SessionLocal() as session:
        if not session.query(Recipe).filter(Recipe.url == url).first():
            raise HTTPException(status_code=404, detail="Recipe not in cache — load it first")
        existing = session.query(SavedRecipe).filter(
            SavedRecipe.user_id == user_id, SavedRecipe.recipe_url == url
        ).first()
        if not existing:
            session.add(SavedRecipe(user_id=user_id, recipe_url=url))
            session.commit()
    return {"saved": True}


@app.delete("/api/saves")
async def unsave_recipe(url: str = Query(...), user: dict = Depends(require_user)):
    url = unquote(url)
    user_id = user["sub"]
    with SessionLocal() as session:
        row = session.query(SavedRecipe).filter(
            SavedRecipe.user_id == user_id, SavedRecipe.recipe_url == url
        ).first()
        if row:
            session.delete(row)
            session.commit()
    return {"saved": False}


@app.get("/api/config")
async def get_config():
    try:
        version = open("VERSION").read().strip()
    except OSError:
        version = "unknown"
    return {"version": version}


# --- Auth routes ---

@app.get("/api/auth/google")
async def auth_google():
    state = secrets.token_urlsafe(16)
    url = await _google.get_authorization_url(
        _GOOGLE_REDIRECT_URI,
        state=state,
        scope=["openid", "email", "profile"],
    )
    response = RedirectResponse(url)
    response.set_cookie("oauth_state", state, max_age=600, httponly=True, samesite="lax")
    return response


@app.get("/api/auth/callback")
async def auth_callback(code: str, state: str, request: Request):
    cookie_state = request.cookies.get("oauth_state")
    if not cookie_state or cookie_state != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    token = await _google.get_access_token(code, _GOOGLE_REDIRECT_URI)
    access_token = token["access_token"]

    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=5,
        )
        r.raise_for_status()
        info = r.json()

    email = info.get("email", "")
    name  = info.get("name", "")

    with SessionLocal() as session:
        user = session.query(User).filter(User.email == email).first()
        if not user:
            user = User(id=str(uuid.uuid4()), email=email, name=name)
            session.add(user)
            session.commit()
            session.refresh(user)
        jwt_token = create_token(user.id, user.email, user.name or "")

    response = RedirectResponse(url=f"{_APP_BASE}/?token={jwt_token}")
    response.delete_cookie("oauth_state")
    return response


class _AuthBody(BaseModel):
    email: str
    password: str


@app.post("/api/auth/signup")
async def signup(body: _AuthBody):
    with SessionLocal() as session:
        if session.query(User).filter(User.email == body.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        user = User(
            id=str(uuid.uuid4()),
            email=body.email,
            hashed_password=hash_password(body.password),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        token = create_token(user.id, user.email, user.name or "")
    return {"token": token, "email": body.email, "name": ""}


@app.post("/api/auth/login")
async def login(body: _AuthBody):
    with SessionLocal() as session:
        user = session.query(User).filter(User.email == body.email).first()
        if not user or not user.hashed_password:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not verify_password(body.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_token(user.id, user.email, user.name or "")
    return {"token": token, "email": body.email, "name": user.name or ""}


# --- SPA routes (serve index.html for all client-side paths) ---

@app.get("/cookbook")
async def serve_cookbook():
    return FileResponse("static/index.html")


# --- static files ---

app.mount("/", StaticFiles(directory="static", html=True), name="static")


# --- helpers ---

def _to_dict(recipe: Recipe, from_cache: bool) -> dict:
    return {
        "url": recipe.url,
        "source": recipe.source,
        "title": recipe.title,
        "description": recipe.description,
        "image_url": recipe.image_url,
        "ingredients": recipe.ingredients or [],
        "method": recipe.method or [],
        "metadata": recipe.metadata_ or {},
        "cached": from_cache,
    }
