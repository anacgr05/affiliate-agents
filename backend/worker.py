import logging
import os

from backend.celery_app import celery_app
from services.image_generator import ImageGenerationError, _RetryableError, generate_hero_image
from services.post_repository import BACKEND_URL, update_post_image

logger = logging.getLogger(__name__)

_IMAGES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "images"
)


def _save_image_locally(post_id: int, image_bytes: bytes) -> str:
    """Persist PNG bytes to data/images/ and return the public URL."""
    os.makedirs(_IMAGES_DIR, exist_ok=True)
    filename = f"post_{post_id}_cover.png"
    filepath = os.path.join(_IMAGES_DIR, filename)
    with open(filepath, "wb") as fh:
        fh.write(image_bytes)
    return f"{BACKEND_URL}/images/{filename}"


@celery_app.task(name="backend.worker.generate_image_task", bind=True, max_retries=3)
def generate_image_task(self, post_id: int, prompt: str) -> str:
    """Generate hero image for a post and update its DB record.

    - Calls DALL-E 3 with exponential backoff (NFR03, NFR06).
    - Saves PNG to data/images/ and returns the public URL (Story-02.03).
    - Marks image_failed after exhausting retries (NFR04).
    """
    logger.info(f"[WORKER] Iniciando job post_id={post_id}")
    try:
        image_bytes = generate_hero_image(prompt)
        public_url = _save_image_locally(post_id, image_bytes)
        update_post_image(post_id, "ready", public_url)
        logger.info(f"[WORKER] Job post_id={post_id} concluído → {public_url}")
        return public_url

    except ImageGenerationError as exc:
        logger.error(f"[WORKER] Job post_id={post_id} falhou definitivamente: {exc}")
        update_post_image(post_id, "image_failed")
        raise

    except _RetryableError as exc:
        logger.warning(f"[WORKER] Erro transiente post_id={post_id}, tentando via Celery: {exc}")
        try:
            raise self.retry(exc=exc, countdown=90)
        except self.MaxRetriesExceededError:
            logger.error(f"[WORKER] Esgotadas tentativas Celery post_id={post_id}")
            update_post_image(post_id, "image_failed")
            raise exc from None

    except Exception as exc:
        logger.error(f"[WORKER] Erro inesperado post_id={post_id}: {exc}")
        update_post_image(post_id, "image_failed")
        raise
