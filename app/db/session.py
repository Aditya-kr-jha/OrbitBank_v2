from typing import Any, AsyncGenerator

try:
    import greenlet
except ImportError:
    raise ImportError(
        "The greenlet library is required for SQLAlchemy async operations. "
        "Please install it using: pip install greenlet"
    )

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from app.config import settings

# Construct the database URL
DATABASE_URL = f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.RDS_ENDPOINT}:{settings.DB_PORT}/{settings.DB_NAME}"
# DATABASE_URL = "sqlite+aiosqlite:///./orbit_bank.db"
# Create the async engine with proper AWS RDS configuration
async_engine = create_async_engine(
    DATABASE_URL,
    echo=settings.ECHO,
    connect_args={
        "timeout": 60,
        "command_timeout": 60,
        "ssl": "require",  # Required for AWS RDS
        "server_settings": {"application_name": "OrbitBank"},
    },
)
# async_engine = create_async_engine(
#     DATABASE_URL,
#     echo=settings.ECHO,
#     connect_args={"check_same_thread": False},  # Required for SQLite
# )
# Create a sessionmaker for async sessions
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def create_db_and_tables_async():
    """Creates database tables asynchronously."""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        print("Database tables created.")
    except Exception as e:
        print(f"Error creating database tables: {e}")
        raise


async def get_async_session() -> AsyncGenerator[Any, Any]:
    """
    Dependency function that yields an async session.
    Ensures the session is closed after the request.
    """
    print("Creating a new async session")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
            print("Async session closed")
