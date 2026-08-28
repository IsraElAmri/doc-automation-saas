"""
Database engine, session factory, and Base declarative class.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config.settings import DATABASE_URL

engine = create_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+psycopg://").replace("postgresql+psycopg2://", "postgresql+psycopg://"),
    pool_pre_ping=True,       # verify connections before handing them out
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()