import os

from sqlalchemy import create_engine, Column, String, JSON, DateTime, Integer, UniqueConstraint, Boolean
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from datetime import datetime, timezone

_DB_URL = os.getenv("DATABASE_URL", "sqlite:///recipes.db")

engine = create_engine(
    _DB_URL,
    connect_args={"check_same_thread": False},
    json_serializer=lambda obj: __import__("json").dumps(obj, ensure_ascii=False),
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id               = Column(String, primary_key=True)
    email            = Column(String, unique=True, nullable=False, index=True)
    hashed_password  = Column(String, nullable=True)   # null for OAuth-only users
    name             = Column(String, nullable=True)
    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, unique=True, index=True, nullable=False)
    source = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, default="")
    image_url = Column(String)
    ingredients = Column(JSON, default=list)
    method = Column(JSON, default=list)
    metadata_ = Column("metadata", JSON, default=dict)
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SavedRecipe(Base):
    __tablename__ = "saved_recipes"
    __table_args__ = (UniqueConstraint("user_id", "recipe_url"),)

    id        = Column(Integer, primary_key=True, autoincrement=True)
    user_id   = Column(String, nullable=False, index=True)
    recipe_url = Column(String, nullable=False)
    saved_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(engine)
