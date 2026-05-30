"""
Builds OpenAI-compatible clients pointed at Modal vLLM endpoints.

Shared config (used by both target and attacker if role-specific vars not set):
  MODAL_VLLM_BASE_URL      — https://you--agentic-red-team-vllm-serve.modal.run
  MODAL_VLLM_API_KEY       — api key configured at deploy time
  MODAL_SERVED_MODEL_NAME  — model alias (default: qwen3.5-9b)
  MODAL_PROXY_TOKEN_ID     — Modal proxy auth token id
  MODAL_PROXY_TOKEN_SECRET — Modal proxy auth token secret

Role-specific overrides (optional — use when target and attacker run different models):
  MODAL_TARGET_VLLM_BASE_URL      / MODAL_ATTACKER_VLLM_BASE_URL
  MODAL_TARGET_VLLM_API_KEY       / MODAL_ATTACKER_VLLM_API_KEY
  MODAL_TARGET_SERVED_MODEL_NAME  / MODAL_ATTACKER_SERVED_MODEL_NAME
"""
import os
from openai import OpenAI


def modal_vllm_client(role: str = "target") -> tuple[OpenAI, str]:
    """Return (OpenAI client, model_name) for the given role ('target' or 'attacker').

    Looks for MODAL_{ROLE}_* vars first, falls back to shared MODAL_* vars.
    """
    prefix = f"MODAL_{role.upper()}_"

    base_url = (
        os.getenv(f"{prefix}VLLM_BASE_URL")
        or os.getenv("MODAL_VLLM_BASE_URL", "")
    ).rstrip("/")

    if not base_url:
        raise ValueError(
            f"No Modal vLLM URL configured for role '{role}'. "
            f"Set {prefix}VLLM_BASE_URL or MODAL_VLLM_BASE_URL in .env."
        )

    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    api_key = (
        os.getenv(f"{prefix}VLLM_API_KEY")
        or os.getenv("MODAL_VLLM_API_KEY")
        or "EMPTY"
    )
    model = (
        os.getenv(f"{prefix}SERVED_MODEL_NAME")
        or os.getenv("MODAL_SERVED_MODEL_NAME", "qwen3.5-9b")
    )

    token_id = os.getenv("MODAL_PROXY_TOKEN_ID")
    token_secret = os.getenv("MODAL_PROXY_TOKEN_SECRET")
    headers = {}
    if token_id and token_secret:
        headers = {"Modal-Key": token_id, "Modal-Secret": token_secret}

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
        default_headers=headers,
        timeout=120,
    )
    return client, model
