"""Database session management."""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker
)

from bot.config import config
from bot.database.models import Base

# Create async engine
engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Initialize database (create all tables).
    
    Note: Use Alembic migrations for schema changes.
    This function is kept for backward compatibility and testing.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize default statuses if they don't exist
    # (for testing or when running without migrations)
    from bot.database.status_manager import init_statuses
    async with AsyncSessionLocal() as session:
        await init_statuses(session)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session.
    
    Usage:
        async with get_session() as session:
            # use session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
