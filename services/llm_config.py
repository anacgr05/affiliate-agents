import os

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "stepfun/step-3.5-flash:free"


def get_openrouter_model() -> str:
    """Return configured OpenRouter model, defaulting to StepFun Step 3.5 Flash free tier."""
    return os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
