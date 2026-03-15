"""Business logic for the FeedPilot analyze feature."""

from app.core.ai import ask_claude
from app.prompts.prompt_manager import get_prompt, get_version


class AnalyzeService:
    """Handles all business logic for product data analysis."""

    async def analyze_question(self, question: str) -> dict[str, str | int]:
        """Analyze a commerce question using Claude.

        Args:
            question: The user's question about product data.

        Returns:
            A dict containing Claude's answer and token usage.

        Raises:
            anthropic.APIError: If the Claude API call fails.
        """
        return ask_claude(
            prompt=question,
            system=get_prompt("feedfixer_v1"),
        )

    def get_active_prompt_version(self) -> str:
        """Return the currently active prompt version.

        Useful for logging and debugging in production.

        Returns:
            Semantic version string of the active prompt.
        """
        return get_version("feedfixer_v1")


def get_analyze_service() -> AnalyzeService:
    """Dependency injection factory for AnalyzeService.

    Returns:
        A ready-to-use AnalyzeService instance.
    """
    return AnalyzeService()