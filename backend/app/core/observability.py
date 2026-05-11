"""AI request observability for FeedPilot.

Provides a structured metadata container and a logging helper for every
AI enrichment request. No database, no external dependencies.

Usage:
    from app.core.observability import AIRequestMetadata, log_ai_request

    metadata = AIRequestMetadata(
        sku_id="SKU-001",
        prompt_name="enrichment_v2",
        prompt_version="2.0.0",
        model="claude-sonnet-4-6",
        model_strategy="cheap",
        target_fields=["brand"],
        use_rag=True,
        input_tokens=512,
        output_tokens=128,
        total_tokens=640,
        status="success",
        error_type=None,
    )
    log_ai_request(metadata)
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Literal

logger = logging.getLogger(__name__)

RequestStatus = Literal["success", "error"]


@dataclasses.dataclass(frozen=True)
class AIRequestMetadata:
    """Immutable metadata snapshot for a single AI enrichment request.

    Captured after ask_claude() returns (or raises) and passed to
    log_ai_request(). Contains the full decision context from the
    enrichment planner alongside token usage and outcome.

    Attributes:
        sku_id:         Product identifier.
        prompt_name:    Logical prompt name (e.g. "enrichment_v2").
        prompt_version: Semantic version of the prompt used.
        model:          Concrete model ID sent to the API.
        model_strategy: Abstract strategy tier from EnrichmentPlan.
        target_fields:  Fields the planner decided to enrich.
        use_rag:        Whether RAG context was fetched for this request.
        input_tokens:   Tokens in the request (0 if ask_claude raised).
        output_tokens:  Tokens in the response (0 if ask_claude raised).
        total_tokens:   Sum of input and output tokens.
        status:         "success" or "error".
        error_type:     Exception class name on error, otherwise None.
    """

    sku_id: str
    prompt_name: str
    prompt_version: str
    model: str
    model_strategy: str
    target_fields: list[str]
    use_rag: bool
    input_tokens: int
    output_tokens: int
    total_tokens: int
    status: RequestStatus
    error_type: str | None


def log_ai_request(metadata: AIRequestMetadata) -> None:
    """Log a single AI request metadata snapshot at INFO level.

    Serialises the metadata to a plain dict via dataclasses.asdict() so
    it is compatible with structured logging formatters (e.g. JSON) without
    requiring them to be configured.

    Args:
        metadata: Completed AIRequestMetadata for the request.
    """
    logger.info("ai_request", extra={"metadata": dataclasses.asdict(metadata)})
