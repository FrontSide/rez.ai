#!/usr/bin/env python3
"""Reindex all cached recipes from SQLite into Elasticsearch.

Run once after deploying the elasticsearch feature:
    docker compose exec rez-ai python reindex.py
"""
import os
from elasticsearch import Elasticsearch
from database import Recipe, SessionLocal, init_db

_ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
_INDEX  = "recipes"

_MAPPING = {
    "mappings": {
        "properties": {
            "url":          {"type": "keyword"},
            "title":        {"type": "text", "analyzer": "standard"},
            "description":  {"type": "text", "analyzer": "standard"},
            "ingredients":  {"type": "text", "analyzer": "standard"},
            "source":       {"type": "keyword"},
            "image_url":    {"type": "keyword", "index": False},
            "cook_time":    {"type": "keyword", "index": False},
            "rating":       {"type": "float"},
            "rating_count": {"type": "integer"},
        }
    }
}


def main():
    init_db()
    es = Elasticsearch([_ES_URL])

    if not es.indices.exists(index=_INDEX):
        es.indices.create(index=_INDEX, **_MAPPING)
        print(f"Created index '{_INDEX}'")

    with SessionLocal() as session:
        recipes = session.query(Recipe).all()

    print(f"Indexing {len(recipes)} recipes...")
    ok = 0
    for recipe in recipes:
        meta = recipe.metadata_ or {}
        doc = {
            "url":          recipe.url,
            "title":        recipe.title,
            "description":  recipe.description or "",
            "ingredients":  recipe.ingredients or [],
            "source":       recipe.source,
            "image_url":    recipe.image_url,
            "cook_time":    meta.get("cook_time") or meta.get("total_time"),
            "rating":       meta.get("rating"),
            "rating_count": meta.get("rating_count"),
        }
        es.index(index=_INDEX, id=recipe.url, document=doc)
        ok += 1

    print(f"Done — {ok} recipes indexed.")


if __name__ == "__main__":
    main()
