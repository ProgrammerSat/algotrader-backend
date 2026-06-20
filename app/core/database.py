import sqlite3
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import get_settings

settings = get_settings()

connect_args = {}
# Only apply local SQLite specific connect arguments
if settings.database_url.startswith("sqlite:///"):
    connect_args = {
        "check_same_thread": False,
        "timeout": 15,
    }

import urllib.parse

db_url = settings.database_url
if "turso.io" in db_url:
    parsed = urllib.parse.urlparse(db_url)
    query = urllib.parse.parse_qs(parsed.query)
    
    if "authToken" in query:
        connect_args["auth_token"] = query["authToken"][0]
        del query["authToken"]
        
    new_query = urllib.parse.urlencode(query, doseq=True)
    new_parsed = parsed._replace(query=new_query)
    db_url = urllib.parse.urlunparse(new_parsed)
    
    if "turso.io/?" in db_url:
        db_url = db_url.replace("turso.io/?", "turso.io?")

if "turso.io" in db_url and "secure=" not in db_url:
    separator = "&" if "?" in db_url else "?"
    db_url += f"{separator}secure=true"

engine = create_engine(
    db_url,
    connect_args=connect_args,
)

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=3000000000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
