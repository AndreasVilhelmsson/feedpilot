"""Business logic for the FeedPilot analyze feature.

This service layer orchestrates AI calls and enforces
business rules independently of HTTP or database concerns.
"""

from app.core.ai import ask_claude

FEEDPILOT_SYSTEM_PROMPT = """
Du är FeedPilot, en AI-expert på e-commerce och produktdata.
Du hjälper e-handlare att förstå och förbättra sin produktdata.
Svara alltid på svenska, var konkret och ge alltid actionable råd.
Formatera svar som JSON när användaren ber om analys.
"""


class AnalyzeService:
    """Handles all business logic for product data analysis.

    Separates AI orchestration from HTTP concerns,
    making it independently testable and reusable.
    """

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
            system=FEEDPILOT_SYSTEM_PROMPT,
        )


def get_analyze_service() -> AnalyzeService:
    """Dependency injection factory for AnalyzeService.

    Returns:
        A ready-to-use AnalyzeService instance.
    """
    return AnalyzeService()