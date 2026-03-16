"""OpenAI embeddings client for FeedPilot.

Uses text-embedding-3-small — best balance of
cost, speed and quality for product data.
"""

from openai import OpenAI
from app.core.config import get_settings

settings = get_settings()

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def get_embeddings_client() -> OpenAI:
    """Return a configured OpenAI client.

    Returns:
        A ready-to-use OpenAI client.
    """
    return OpenAI(api_key=settings.openai_api_key)


def create_embedding(text: str) -> list[float]:
    """Create a vector embedding for a text string.

    Args:
        text: The text to embed.

    Returns:
        A list of floats representing the embedding vector.

    Raises:
        openai.APIError: If the API call fails.
    """
    client = get_embeddings_client()
    text = text.replace("\n", " ").strip()
    response = client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding