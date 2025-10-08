# db/session.py
import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine
)
from sqlalchemy.pool import NullPool
from .config import get_db_settings

# Global engine and session factory
_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker] = None
_init_lock = asyncio.Lock()


async def init_db(use_direct: bool = False) -> AsyncEngine:
    """
    Initialize database engine and session factory.
    Does NOT create tables - use Alembic migrations instead.
    
    Args:
        use_direct: If True, use direct connection.
                   If False, use pooled connection (default for app).
    """
    global _engine, _session_factory
    
    async with _init_lock:
        if _engine is not None:
            print("✓ Database already initialized")
            return _engine
        
        print("INFO: Initializing database connection...")
        settings = get_db_settings()
        connection_url = settings.get_connection_url(use_direct=use_direct)
        print(f"✓ Connection URL built (use_direct={use_direct})")
        
        # Supabase-specific connection arguments for asyncpg
        # Required to work with Supavisor (Supabase's pooler)
        connect_args = {
            # Disable prepared statements (required for Supavisor)
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            # Use unique prepared statement names to avoid conflicts
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
        }
        
        # For pooled connections (Supavisor), use NullPool
        # For direct connections, use default pooling
        poolclass = NullPool if not use_direct else None
        
        _engine = create_async_engine(
            connection_url,
            echo=settings.ECHO_SQL,
            pool_pre_ping=settings.POOL_PRE_PING,
            poolclass=poolclass,
            connect_args=connect_args,
            # Only set pool_size for direct connections
            **({"pool_size": settings.POOL_SIZE, "max_overflow": settings.MAX_OVERFLOW} if use_direct else {})
        )
        print("✓ Database engine created")
        
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
        print("✓ Session factory created")
        print("⚠️  Remember to run migrations with: alembic upgrade head")
        
        return _engine


async def get_engine() -> AsyncEngine:
    """Get or create database engine"""
    if _engine is None:
        await init_db()
    return _engine


def get_session_factory() -> async_sessionmaker:
    """Get session factory (engine must be initialized first)"""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions.
    Use this in your tools for database operations.
    
    Example:
        async with get_db_session() as session:
            repo = FileRepository(session)
            await repo.save_file_version(...)
    """
    if _session_factory is None:
        await init_db()
    
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_db():
    """Close database connections"""
    global _engine, _session_factory
    
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
