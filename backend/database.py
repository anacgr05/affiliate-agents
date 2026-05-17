import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, JSON, DateTime
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://affiliate_user:affiliate_password@localhost:5432/affiliate_db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)
    title = Column(String)
    content = Column(String)
    metadata_json = Column(JSON, default={})
    image_url = Column(String, nullable=True)
    image_status = Column(String, default="image_pending") # image_pending, image_failed, ready
    created_at = Column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
