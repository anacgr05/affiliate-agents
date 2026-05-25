import os
from datetime import datetime

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
)

from sqlalchemy.orm import (
    sessionmaker,
    declarative_base,
)

from sqlalchemy import (
    Column,
    Integer,
    String,
    JSON,
    DateTime,
)

# Só usa banco se DATABASE_URL estiver configurada
DATABASE_URL = os.getenv("DATABASE_URL")

engine = None
AsyncSessionLocal = None

if DATABASE_URL:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
    )

    AsyncSessionLocal = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

Base = declarative_base()


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)

    slug = Column(
        String,
        unique=True,
        index=True,
    )

    title = Column(String)

    content = Column(String)

    metadata_json = Column(
        JSON,
        default={},
    )

    image_url = Column(
        String,
        nullable=True,
    )

    image_status = Column(
        String,
        default="image_pending",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


async def init_db():
    if not engine:
        print("DATABASE_URL não configurado — usando JSON/local storage")
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    if not AsyncSessionLocal:
        return

    async with AsyncSessionLocal() as session:
        yield session
