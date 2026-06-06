"""
Async SQLAlchemy engine and session factory.

Usage (in FastAPI dependency):
    async with get_async_session() as session:
        ...

Usage in Celery tasks (sync context):
    Use get_sync_session() which wraps async in asyncio.run().
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from agents.config import DATABASE_TARGET

# ---------------------------------------------------------------------------
# Build asyncpg connection URL from existing DATABASE_TARGET dict
# ---------------------------------------------------------------------------


def _build_async_url() -> str:
    cfg = DATABASE_TARGET
    return (
        f"postgresql+asyncpg://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['dbname']}"
    )


# Engine is created once at module import
_engine = create_async_engine(
    _build_async_url(),
    echo=False,            # set True for SQL debug logging
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,    # validates connections before use
)

# Session factory
_async_session_factory = async_sessionmaker(
    bind=_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ---------------------------------------------------------------------------
# Context manager for use in FastAPI route dependencies
# ---------------------------------------------------------------------------


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a new AsyncSession; commits on success, rolls back on error."""
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# FastAPI dependency (use with Depends)
# ---------------------------------------------------------------------------


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession per request."""
    async with get_async_session() as session:
        yield session


# ---------------------------------------------------------------------------
# Sync helper for Celery tasks (runs in a thread-event-loop)
# ---------------------------------------------------------------------------


def run_in_new_loop(coro):
    """Run an async coroutine synchronously — for use inside Celery tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Engine teardown (call on app shutdown)
# ---------------------------------------------------------------------------


async def close_engine() -> None:
    await _engine.dispose()
