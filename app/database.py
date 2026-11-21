import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///civicloop.db")

# For SQLite, keep the check_same_thread workaround
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, echo=False)

# Enable PostGIS if using PostgreSQL
if DATABASE_URL.startswith("postgresql"):
    @event.listens_for(engine, "connect", insert=True)
    def enable_postgis(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        try:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            dbapi_conn.commit()
        except Exception:
            pass  # Extension might already exist
        finally:
            cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
