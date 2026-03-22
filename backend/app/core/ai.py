"""AI client module for FeedPilot.

Provides a factory function and a high-level wrapper
for communicating with the Anthropic Claude API.
"""
import json
import re
import anthropic
from app.core.config import get_settings

settings = get_settings()


def get_client() -> anthropic.Anthropic:
    """Return a configured Anthropic client instance.

    Creates a new client on each call using the API key
    from application settings. This pattern supports
    easy mocking in tests.

    Returns:
        A ready-to-use Anthropic client.
    """
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)

def _strip_markdown(text: str) -> str:
    """Strip markdown code fences if model returns them.

    Args:
        text: Raw model output.

    Returns:
        Clean JSON string without markdown wrapping.
    """
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
        anthropic.APIError: If the API call fails.
    """
    client = get_client()
    kwargs: dict = {
        "model": "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    text = response.content[0].text

    return {
        "answer": text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
    }


def ask_claude_vision(
    image_data: str,
    media_type: str,
    prompt: str,
    system: str = "",
    max_tokens: int = 2000,
) -> dict[str, str | int]:
    """Send an image + text prompt to Claude and return the response.

    Uses the Anthropic multimodal content format to pass a base64-encoded
    image alongside a text prompt. The image is processed before the text
    in the content list so Claude sees the visual context first.

    Args:
        image_data: Base64-encoded image bytes as a string.
        media_type: MIME type of the image, e.g. 'image/jpeg' or 'image/png'.
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
        anthropic.APIError: If the API call fails.
    """
    client = get_client()

    content: list[dict] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_data,
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

    response = client.messages.create(**kwargs)
    text = response.content[0].text

    return {
        "answer": text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
    }