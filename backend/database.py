from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .config import SYNC_DATABASE_URL
from .models import Base

engine = create_engine(SYNC_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
