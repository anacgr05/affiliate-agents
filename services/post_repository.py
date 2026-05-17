"""Sync SQLAlchemy repository for Post persistence.

Used by LangGraph nodes (sync, thread-pool context) and the Celery worker.
FastAPI endpoints use AsyncSessionLocal from backend.database directly.
"""

import json
import logging
import os
from datetime import datetime

from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker, Session

from backend.database import Base, Post

logger = logging.getLogger(__name__)

_SYNC_DATABASE_URL = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://affiliate_user:affiliate_password@localhost:5432/affiliate_db",
)

_engine = create_engine(_SYNC_DATABASE_URL, pool_pre_ping=True)
_SessionFactory: sessionmaker[Session] = sessionmaker(bind=_engine)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def ensure_tables_exist() -> None:
    Base.metadata.create_all(_engine)


def save_post(article_data: dict[str, object]) -> int:
    """Persist a new post and return its DB id. Sets image_status='image_pending'."""
    slug: str = str(article_data.get("slug", ""))
    title: str = str(article_data.get("title", ""))

    with _SessionFactory() as session:
        existing = session.query(Post).filter_by(slug=slug).first()
        if existing is not None:
            existing.title = title
            existing.metadata_json = article_data  # type: ignore[assignment]
            existing.image_status = "image_pending"
            existing.image_url = None
            session.commit()
            session.refresh(existing)
            logger.info(f"Post updated in DB: slug={slug} id={existing.id}")
            return int(existing.id)

        post = Post(
            slug=slug,
            title=title,
            content=json.dumps(article_data, ensure_ascii=False),
            metadata_json=article_data,
            image_status="image_pending",
            image_url=None,
            created_at=datetime.utcnow(),
        )
        session.add(post)
        session.commit()
        session.refresh(post)
        logger.info(f"Post saved to DB: slug={slug} id={post.id}")
        return int(post.id)


def update_post_image(post_id: int, image_status: str, image_url: str | None = None) -> None:
    """Update image_status and optionally image_url for a post (Epic-02 Story-02.03)."""
    with _SessionFactory() as session:
        values: dict[str, object] = {"image_status": image_status}
        if image_url is not None:
            values["image_url"] = image_url
        session.execute(update(Post).where(Post.id == post_id).values(**values))
        session.commit()
    logger.info(f"Post {post_id} image updated: status={image_status} url={image_url}")


def get_all_posts() -> list[dict[str, object]]:
    """Return all posts from DB, merging image_status and image_url into metadata_json."""
    with _SessionFactory() as session:
        rows = session.query(Post).order_by(Post.created_at.desc()).all()
        result: list[dict[str, object]] = []
        for row in rows:
            data: dict[str, object] = dict(row.metadata_json) if row.metadata_json else {}
            data["image_status"] = row.image_status
            data["image_url"] = row.image_url
            result.append(data)
        return result
