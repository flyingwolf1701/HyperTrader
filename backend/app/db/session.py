import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.base import Base

logger = logging.getLogger(__name__)

# --- FIX: Pass SSL arguments separately for the asyncpg driver ---
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    future=True,
    connect_args={"ssl": "require"} # This is the correct way to pass sslmode
)
# --- END FIX ---

# Create a configured "AsyncSession" class
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def init_db():
    """Initialize the database and create tables if they don't exist."""
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created/verified")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise

async def get_db_session() -> AsyncSession:
    """FastAPI dependency to get a database session for a single request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def close_db_connection():
    """
    Closes the database connection pool. This is called during application shutdown.
    """
    logger.info("Closing database connection pool.")
    await engine.dispose()
