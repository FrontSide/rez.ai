import asyncio
import os
from contextlib import asynccontextmanager
from urllib.parse import unquote

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from auth import require_user
from database import Recipe, SavedRecipe, SessionLocal, init_db
from scraper import bbc_good_food


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="rez.ai", lifespan=lifespan)


# --- API routes (must be registered before static mount) ---

_FEATURED_QUERIES = ["pasta", "chicken", "chocolate cake", "salad"]

@app.get("/api/featured")
async def featured_recipes():
    tasks = [asyncio.to_thread(bbc_good_food.search, q) for q in _FEATURED_QUERIES]
    results_lists = await asyncio.gather(*tasks, return_exceptions=True)

    seen: set[str] = set()
    combined: list[dict] = []
    max_len = max((len(r) for r in results_lists if isinstance(r, list)), default=0)
    for i in range(max_len):
        for r in results_lists:
            if isinstance(r, list) and i < len(r) and r[i]["url"] not in seen:
                seen.add(r[i]["url"])
                combined.append(r[i])

    return {"results": combined[:12]}


@app.get("/api/search")
async def search_recipes(q: str = Query(..., min_length=1)):
    try:
        results = await asyncio.to_thread(bbc_good_food.search, q)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")
    return {"query": q, "results": results}


@app.get("/api/recipe")
async def get_recipe(url: str = Query(...)):
    url = unquote(url)

    with SessionLocal() as session:
        cached = session.query(Recipe).filter(Recipe.url == url).first()
        if cached:
            return _to_dict(cached, from_cache=True)

    try:
        data = await asyncio.to_thread(bbc_good_food.scrape_recipe, url)
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
    return {
        "supabase_url":      os.getenv("SUPABASE_URL", ""),
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
        "version":           version,
    }


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
