from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
from app.core.logger import app_logger


def _build_engine_url():
    """
    Build MySQL URL safely.
    Handles special characters in password (like #, @, etc.)
    by using sqlalchemy.engine.URL instead of raw string.
    """
    from sqlalchemy.engine import URL
    from app.core.config import settings as s

    return URL.create(
        drivername="mysql+aiomysql",
        username=s.DB_USER,
        password=s.DB_PASSWORD,   # SQLAlchemy handles special chars automatically
        host=s.DB_HOST,
        port=s.DB_PORT,
        database=s.DB_NAME,
    )


# Async engine
engine = create_async_engine(
    _build_engine_url(),
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            app_logger.error(f"Database session error: {e}")
            raise
        # No explicit session.close() — the `async with` context manager handles it


async def create_all_tables():
    async with engine.begin() as conn:
        from app.models import user, search, product, agent_log, order  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
    app_logger.info("All database tables created successfully.")
