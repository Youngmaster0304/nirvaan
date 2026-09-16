import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    pass


DATABASE_URL = settings.DATABASE_URL

if DATABASE_URL.startswith("postgresql"):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    
    db_url = DATABASE_URL
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(db_url, echo=settings.DEBUG, pool_pre_ping=True, pool_size=10, max_overflow=20)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async def get_db():
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()
    
    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    DB_TYPE = "postgresql"
else:
    SQLITE_PATH = DATABASE_URL.replace("sqlite:///", "") if DATABASE_URL.startswith("sqlite") else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "railvision.db")
    
    engine = create_engine(f"sqlite:///{SQLITE_PATH}", echo=False)
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    
    def get_db_sync():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    async def init_db():
        Base.metadata.create_all(bind=engine)
    
    async def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    DB_TYPE = "sqlite"
