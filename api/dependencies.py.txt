"""
FastAPI dependency providers.

- db_session: async SQLAlchemy session per request
- get_current_user: JWT authentication (dev mode accepts any token)
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from agents.config import API_KEY
from db.session import get_async_session

# ---------------------------------------------------------------------------
# Database session dependency
# ---------------------------------------------------------------------------


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields one AsyncSession per request, committed or rolled back on exit."""
    async with get_async_session() as session:
        yield session


# ---------------------------------------------------------------------------
# API Key Auth dependency
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Validates Bearer API Key and returns a mock user payload.

    In production: Replace this with your actual SSO/OIDC integration.
    In dev: Use 'dev-api-key-change-in-prod' as the Bearer token.
    """
    token = credentials.credentials
    if token != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Return a mock user ID for the audit logs
    return {"user_id": "api-user", "name": "API User"}
