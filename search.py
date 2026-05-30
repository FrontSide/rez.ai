import logging
import os

from elasticsearch import AsyncElasticsearch, NotFoundError

logger = logging.getLogger(__name__)

_ES_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
_INDEX  = "recipes"

es = AsyncElasticsearch([_ES_URL])

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


async def ensure_index():
    try:
        exists = await es.indices.exists(index=_INDEX)
        if not exists:
            await es.indices.create(index=_INDEX, **_MAPPING)
            logger.info("Created Elasticsearch index '%s'", _INDEX)
    except Exception as e:
        logger.warning("Could not ensure ES index: %s", e)


async def index_recipe(recipe: dict):
    meta = recipe.get("metadata") or {}
    doc = {
        "url":          recipe["url"],
        "title":        recipe.get("title", ""),
        "description":  recipe.get("description", ""),
        "ingredients":  recipe.get("ingredients") or [],
        "source":       recipe.get("source", ""),
        "image_url":    recipe.get("image_url"),
        "cook_time":    meta.get("cook_time") or meta.get("total_time"),
        "rating":       meta.get("rating"),
        "rating_count": meta.get("rating_count"),
    }
    try:
        await es.index(index=_INDEX, id=doc["url"], document=doc)
    except Exception as e:
        logger.warning("Could not index recipe '%s': %s", doc["url"], e)


async def search(q: str) -> list[dict]:
    try:
        resp = await es.search(
            index=_INDEX,
            query={
                "multi_match": {
                    "query":     q,
                    "fields":    ["title^3", "ingredients^2", "description"],
                    "fuzziness": "AUTO",
                }
            },
            size=20,
        )
        return [_to_card(h["_source"]) for h in resp["hits"]["hits"]]
    except Exception as e:
        logger.warning("ES search failed: %s", e)
        return []


def _to_card(doc: dict) -> dict:
    return {
        "url":          doc.get("url", ""),
        "title":        doc.get("title", ""),
        "image_url":    doc.get("image_url"),
        "description":  doc.get("description", ""),
        "cook_time":    doc.get("cook_time"),
        "rating":       doc.get("rating"),
        "rating_count": doc.get("rating_count"),
        "source":       doc.get("source", ""),
    }
