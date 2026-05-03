import os

from sqlalchemy import create_engine, Column, String, JSON, DateTime, Integer
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


def init_db():
    Base.metadata.create_all(engine)
