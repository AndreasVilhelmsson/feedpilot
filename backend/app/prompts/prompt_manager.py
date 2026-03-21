"""Prompt version manager for FeedPilot.

Centralizes prompt loading and versioning so prompts
can be updated, rolled back and tracked independently
of application code — following the principle of treating
prompts as software artifacts with version control.
"""

from app.prompts.versions import v1_feedfixer, v2_enrichment


PROMPT_REGISTRY: dict[str, object] = {
    "feedfixer_v1": v1_feedfixer,
    "enrichment_v2": v2_enrichment,
}


def get_prompt(name: str) -> str:
    """Return the system prompt for the given prompt name.

    Args:
        name: Registered prompt name, e.g. 'feedfixer_v1'.

    Returns:
        The system prompt string.

    Raises:
        KeyError: If the prompt name is not registered.
    """
    if name not in PROMPT_REGISTRY:
        raise KeyError(
            f"Prompt '{name}' not found. "
            f"Available prompts: {list(PROMPT_REGISTRY.keys())}"
        )
    return PROMPT_REGISTRY[name].SYSTEM_PROMPT


def get_version(name: str) -> str:
    """Return the version string for the given prompt.

    Args:
        name: Registered prompt name.

    Returns:
        Semantic version string, e.g. '1.0.0'.

    Raises:
        KeyError: If the prompt name is not registered.
    """
    if name not in PROMPT_REGISTRY:
        raise KeyError(f"Prompt '{name}' not found.")
    return PROMPT_REGISTRY[name].VERSION


def list_prompts() -> list[str]:
    """Return all registered prompt names.

    Returns:
        List of available prompt names.
    """
    return list(PROMPT_REGISTRY.keys())