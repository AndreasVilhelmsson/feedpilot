"""Pydantic schemas for the analyze endpoint.

Separates data validation models from route logic
following FastAPI best practice for larger applications.
"""

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request body for the analyze endpoint."""

    question: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="The question or product data to analyze.",
        examples=["Vilka produkter har högst returgrad?"],
    )


class AnalyzeResponse(BaseModel):
    """Response from the analyze endpoint."""

    answer: str = Field(description="Claude's response in Swedish.")
    input_tokens: int = Field(description="Tokens consumed by the request.")
    output_tokens: int = Field(description="Tokens consumed by the response.")
    total_tokens: int = Field(description="Total tokens consumed.")