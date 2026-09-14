from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import settings

DB_URL = settings.resolved_database_url()

if DB_URL.startswith("sqlite"):
    # SQLite is single-connection-per-thread by default; FastAPI may serve a
    # request from a different thread than the one that opened the connection.
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DB_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()