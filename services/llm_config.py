import os

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "google/gemini-2.5-flash"

# Timeouts calibrated from real pipeline measurements (stepfun free tier):
#   CEO: ~28s | Portfolio analyze: ~20s | Product Manager: ~8s
#   Critic: ~18s | Writer: ~38s
# Using 2x headroom to handle variance without infinite hangs.
LLM_TIMEOUT_SHORT = 45   # Product Manager, Analyst (~8-15s calls)
LLM_TIMEOUT_MEDIUM = 60  # CEO, Portfolio analyze, Critic (~18-28s calls)
LLM_TIMEOUT_LONG = 90    # Writer (~38s calls, most complex prompt)


def get_openrouter_model() -> str:
    """Return configured OpenRouter model, defaulting to Gemini 2.5 Flash."""
    return os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)
