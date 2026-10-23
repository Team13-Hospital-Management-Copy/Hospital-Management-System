import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .tls import check_database_tls

# SRS 3.3 calls for an RDBMS (e.g. MySQL/PostgreSQL) in production; SQLite is used
# here for local development and tests. Point DATABASE_URL at a real RDBMS to switch.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./hms.db")

# US-02 / HMS-SR-001: a networked database must be reached over TLS.
check_database_tls(DATABASE_URL)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
