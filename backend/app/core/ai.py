"""AI client module for FeedPilot.

Provides a factory function and a high-level wrapper
for communicating with the Anthropic Claude API.
"""
import base64
import time
import re

import anthropic

from app.core.config import get_settings
from app.core.image import prepare_image_for_vision

MAX_RETRIES = 4
RETRY_DELAYS = [2, 5, 10, 20]

settings = get_settings()


def get_client() -> anthropic.Anthropic:
    """Return a configured Anthropic client instance."""
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _strip_markdown(text: str) -> str:
    """Strip markdown code fences if model returns them."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def ask_claude(
    prompt: str,
    system: str | None = None,
    max_tokens: int = 1000,
) -> dict[str, str | int]:
    """Send a prompt to Claude and return the response with token usage.

    Args:
        prompt: The user message to send to the model.
        system: Optional system prompt that sets Claude's behavior.
        max_tokens: Maximum tokens in the model response.

    Returns:
        A dict with keys:
            answer: Claude's text response.
            input_tokens: Number of tokens in the request.
            output_tokens: Number of tokens in the response.
            total_tokens: Sum of input and output tokens.

    Raises:
        anthropic.APIError: If the API call fails after all retries.
        RuntimeError: If the model truncates the response.
    """
    client = get_client()
    kwargs: dict = {
        "model": "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    for attempt, delay in enumerate(RETRY_DELAYS, 1):
        try:
            response = client.messages.create(**kwargs)
            if response.stop_reason == "max_tokens":
                raise RuntimeError(
                    f"Claude svarade med stop_reason='max_tokens' — svaret trunkerades. "
                    f"Öka max_tokens (nuvarande: {max_tokens}). "
                    f"Output-tokens: {response.usage.output_tokens}."
                )
            text = response.content[0].text
            return {
                "answer": text,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }
        except anthropic.APIStatusError as e:
            if e.status_code != 529 or attempt >= MAX_RETRIES:
                raise
            print(f"API överbelastad, försök {attempt}/{MAX_RETRIES}. Väntar {delay}s...")
            time.sleep(delay)


def ask_claude_vision(
    image_data: bytes,
    prompt: str,
    system: str = "",
    max_tokens: int = 2000,
) -> dict[str, str | int]:
    """Send an image + text prompt to Claude and return the response.

    Converts and resizes the image via prepare_image_for_vision before
    sending. Handles JPEG, PNG, WebP and AVIF (ffmpeg fallback).

    Args:
        image_data: Raw image bytes in any supported format.
        prompt: Text instruction describing what Claude should do with the image.
        system: Optional system prompt that sets Claude's behaviour.
        max_tokens: Maximum tokens in the model response.

    Returns:
        A dict with keys:
            answer: Claude's text response.
            input_tokens: Number of tokens in the request.
            output_tokens: Number of tokens in the response.
            total_tokens: Sum of input and output tokens.

    Raises:
        anthropic.APIError: If the API call fails after all retries.
        ValueError: If the image cannot be converted.
    """
    image_bytes, converted_media_type = prepare_image_for_vision(image_data)
    b64 = base64.standard_b64encode(image_bytes).decode()

    client = get_client()
    content: list[dict] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": converted_media_type,
                "data": b64,
            },
        },
        {"type": "text", "text": prompt},
    ]

    kwargs: dict = {
        "model": "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    if system:
        kwargs["system"] = system

    for attempt, delay in enumerate(RETRY_DELAYS, 1):
        try:
            response = client.messages.create(**kwargs)
            text = response.content[0].text
            return {
                "answer": text,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            }
        except anthropic.APIStatusError as e:
            if e.status_code != 529 or attempt >= MAX_RETRIES:
                raise
            print(f"API överbelastad, försök {attempt}/{MAX_RETRIES}. Väntar {delay}s...")
            time.sleep(delay)