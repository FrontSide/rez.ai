import asyncio
from contextlib import asynccontextmanager
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import Recipe, SessionLocal, init_db
from scraper import bbc_good_food


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="rez.ai", lifespan=lifespan)


# --- API routes (must be registered before static mount) ---

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
