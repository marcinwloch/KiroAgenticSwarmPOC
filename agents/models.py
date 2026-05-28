from __future__ import annotations

import os

from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.models.model import CacheConfig

# Bedrock in eu-central-1 requires inference profile IDs (eu.* / global.*), not bare model IDs.
_INFERENCE_PROFILE_DEFAULTS: dict[str, str] = {
    "architect": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "developer": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
    # Haiku intermittently fails marketplace auth on runtime role; Sonnet matches developer.
    "tester": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "reviewer": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "judge": "eu.amazon.nova-lite-v1:0",
}

# Bare foundation-model IDs → EU inference profile (common misconfiguration).
_BARE_TO_EU_PROFILE: dict[str, str] = {
    "amazon.nova-lite-v1:0": "eu.amazon.nova-lite-v1:0",
    "amazon.nova-micro-v1:0": "eu.amazon.nova-micro-v1:0",
    "amazon.nova-pro-v1:0": "eu.amazon.nova-pro-v1:0",
    "anthropic.claude-sonnet-4-5-20250929-v1:0": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "anthropic.claude-haiku-4-5-20251001-v1:0": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
}


def _region() -> str:
    return os.environ.get("AWS_REGION", "eu-central-1")


# Inter-agent workers receive trusted context (spec + prior agent outputs). Applying
# PROMPT_ATTACK guardrails to that context causes false positives (e.g. architect
# threat-model sections with "DoS", "brute-force", "attack").
_GUARDRAIL_EXTERNAL_ROLES = frozenset({"architect", "reviewer"})


def _guardrail_config(role: str) -> dict:
    guardrail_id = os.environ.get("SWARM_GUARDRAIL_ID", "").strip()
    if not guardrail_id:
        return {}
    if role not in _GUARDRAIL_EXTERNAL_ROLES:
        return {}
    return {
        "guardrail_id": guardrail_id,
        "guardrail_version": "DRAFT",
        "guardrail_trace": "enabled",
    }


def normalize_model_id(model_id: str) -> str:
    """Map bare Bedrock model IDs to inference profile IDs when needed."""
    model_id = model_id.strip()
    if model_id.startswith("arn:aws:bedrock:") and "inference-profile/" in model_id:
        return model_id.rsplit("/", 1)[-1]
    if model_id in _BARE_TO_EU_PROFILE:
        return _BARE_TO_EU_PROFILE[model_id]
    if model_id.startswith(("eu.", "us.", "global.")):
        return model_id
    # Unknown bare ID — prefix with eu. for cross-region inference in Frankfurt PoC.
    if "." in model_id and not model_id.startswith(("eu.", "us.", "global.")):
        return f"eu.{model_id}"
    return model_id


def worker_model_id(role: str) -> str:
    env_key = f"SWARM_MODEL_{role.upper()}"
    raw = os.environ.get(env_key, _INFERENCE_PROFILE_DEFAULTS.get(role, _INFERENCE_PROFILE_DEFAULTS["developer"]))
    return normalize_model_id(raw)


def make_agent(name: str, system_prompt: str, role: str) -> Agent:
    model_id = worker_model_id(role)
    model = BedrockModel(
        model_id=model_id,
        region_name=_region(),
        cache_config=CacheConfig(strategy="auto"),
        **_guardrail_config(role),
    )
    return Agent(model=model, name=name, system_prompt=system_prompt)
