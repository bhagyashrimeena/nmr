import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None):
    db_url = url or os.getenv("NMR_DB_URL", "sqlite:///./nmr_demo.db")
    return create_engine(db_url, connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {})


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
