import base64
import logging
import os

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_OPENROUTER_CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_IMAGE_MODEL = "google/gemini-3.1-flash-image-preview"
_FALLBACK_PROMPT = (
    "Professional product review hero image, clean modern design, "
    "tech products, vibrant colors, high quality photography style"
)

# Prefixed to every prompt to enforce landscape/banner composition.
_LANDSCAPE_PREFIX = (
    "Generate a wide landscape image in 16:9 aspect ratio, horizontal banner format "
    "suitable for a blog hero section (approximately 1280x720). "
    "Fill the entire width with the composition. "
)



class ImageGenerationError(Exception):
    pass


class _RetryableError(Exception):
    pass


def _extract_image_bytes(response_data: dict) -> bytes:
    """Parse OpenRouter's chat response and return raw image bytes.

    Handles two layouts that different providers use:
      1. OpenAI-style:  choices[0].message.images[0].image_url.url
      2. Gemini-style:  choices[0].message.content[i].image_url.url  (type == "image_url")
    Both carry a data URI: "data:image/<fmt>;base64,<b64>"
    """
    try:
        message = response_data["choices"][0]["message"]

        # Format 1 — OpenAI image models (gpt-image-*)
        images = message.get("images")
        if images:
            data_url: str = images[0]["image_url"]["url"]
            return base64.b64decode(data_url.split(",", 1)[1])

        # Format 2 — Gemini / content-parts layout
        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    data_url = part["image_url"]["url"]
                    return base64.b64decode(data_url.split(",", 1)[1])

        raise ImageGenerationError(
            f"Nenhum campo de imagem reconhecido. Campos da mensagem: {list(message.keys())}"
        )
    except (KeyError, IndexError, TypeError) as exc:
        raise ImageGenerationError(f"Resposta inesperada do OpenRouter: {exc}") from exc


@retry(
    wait=wait_exponential(multiplier=1, min=4, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(_RetryableError),
    reraise=True,
)
def generate_hero_image(prompt: str) -> bytes:
    """Generate a hero image via OpenRouter (chat/completions) and return raw PNG bytes.

    Uses OPENROUTER_API_KEY. Retries up to 3x on rate limits (NFR03).
    Raises ImageGenerationError on unrecoverable failures (NFR04).
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ImageGenerationError("OPENROUTER_API_KEY não configurado")

    model = os.getenv("OPENROUTER_IMAGE_MODEL", _DEFAULT_IMAGE_MODEL)
    safe_prompt = _LANDSCAPE_PREFIX + (prompt or _FALLBACK_PROMPT)

    try:
        resp = requests.post(
            _OPENROUTER_CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://affiliate-agents.local",
                "X-Title": "Affiliate Agents",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": safe_prompt}],
            },
            timeout=(10, 180),
            stream=False,
        )
        resp.raise_for_status()
    except (
        requests.exceptions.Timeout,
        requests.exceptions.ChunkedEncodingError,
        requests.exceptions.ConnectionError,
    ) as exc:
        logger.warning(f"Erro de rede recuperável — tentando novamente: {exc}")
        raise _RetryableError(str(exc)) from exc
    except requests.exceptions.HTTPError as exc:
        if resp.status_code == 429:
            logger.warning("Rate limit atingido — tentando novamente")
            raise _RetryableError("429 rate limit") from exc
        raise ImageGenerationError(f"OpenRouter retornou {resp.status_code}: {resp.text[:200]}") from exc
    except requests.exceptions.RequestException as exc:
        raise ImageGenerationError(f"Erro de rede: {exc}") from exc

    return _extract_image_bytes(resp.json())
