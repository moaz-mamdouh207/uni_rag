from typing import Generator, AsyncGenerator
from contextlib import contextmanager


from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


from db.relational.exceptions import (
    DatabaseError,
    DBIntegrityError, 
)

from core.config import settings


# ───────────────────────────────── Async Session for fastapi ──────────────────────────────────

async_engine = create_async_engine(
    settings.relational_db.async_url,
    echo=settings.relational_db.echo,
    pool_size=settings.relational_db.pool_size,
    max_overflow=settings.relational_db.max_overflow,
    pool_pre_ping=True,
    pool_recycle=3600,
)

async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides transactional async DB sessions."""
    async with async_session_factory() as session:
        try:
            yield session
        except IntegrityError as exc:
            await session.rollback()
            raise DBIntegrityError(str(exc.orig)) from exc
        except SQLAlchemyError as exc:
            await session.rollback()
            raise DatabaseError(str(exc)) from exc
        except Exception:
            await session.rollback()
            raise


# ───────────────────────────────── Sync Session for Celery ──────────────────────────────────

engine = create_engine(
    settings.relational_db.sync_url,
    echo=settings.relational_db.echo,
    pool_size=settings.relational_db.pool_size,
    max_overflow=settings.relational_db.max_overflow,
    pool_pre_ping=True,
    pool_recycle=3600,
)

session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_sync_db() -> Generator[Session, None, None]:
    """Transactional sync session for Celery/background tasks."""
    with session_factory() as session:
        try:
            yield session
        except IntegrityError as exc:
            session.rollback()
            raise DBIntegrityError(str(exc.orig)) from exc
        except SQLAlchemyError as exc:
            session.rollback()
            raise DatabaseError(str(exc)) from exc
        except Exception:
            session.rollback()
            raise
