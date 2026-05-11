"""Minimal AI payload builder for FeedPilot enrichment.

Builds the input dict sent to Claude for a single enrichment task.
Only fields that are relevant context for the given missing_fields are
included — derived from FIELD_REGISTRY, not from prompt text.

Usage:
    from app.services.payload_builder import build_enrichment_payload

    payload = build_enrichment_payload(canonical, missing_fields, rag_context)
    user_message = json.dumps(payload, ensure_ascii=False)
"""

from __future__ import annotations

from typing import Any

from app.schemas.canonical import CanonicalProduct
from app.services.field_metadata import get_field_meta

# Canonical field name -> payload key when the two differ.
# All other fields use their canonical name as the payload key.
_CANONICAL_TO_PAYLOAD_KEY: dict[str, str] = {
    "extra_attributes": "attributes",
}


def build_enrichment_payload(
    canonical: CanonicalProduct,
    missing_fields: list[str],
    rag_context: list[dict],
) -> dict[str, Any]:
    """Build a minimal Claude input payload for the given enrichment task.

    Looks up context_fields for each entry in missing_fields via
    FIELD_REGISTRY and takes the union. Only those fields are included
    in the product dict. Unknown or unregistered missing_fields are
    silently ignored.

    sku_id is always present for identification regardless of context_fields.

    Args:
        canonical:      CanonicalProduct representation of the product.
        missing_fields: Core fields that are missing and must be enriched.
        rag_context:    Semantically similar products from RAG search.

    Returns:
        Dict with keys: product, rag_context, missing_fields,
        enrichment_instruction. Caller is responsible for json.dumps().
    """
    context_field_union: set[str] = set()
    for field_name in missing_fields:
        meta = get_field_meta(field_name)
        if meta is None:
            continue
        context_field_union.update(meta.context_fields)

    product: dict[str, Any] = {"sku_id": canonical.sku_id}
    for canonical_field in context_field_union:
        payload_key = _CANONICAL_TO_PAYLOAD_KEY.get(canonical_field, canonical_field)
        product[payload_key] = getattr(canonical, canonical_field, None)

    return {
        "product": product,
        "rag_context": [
            {
                "sku_id": ctx["sku_id"],
                "title": ctx["title"],
                "category": ctx["category"],
                "attributes": ctx["attributes"],
                "similarity": ctx["similarity"],
            }
            for ctx in rag_context
        ],
        "missing_fields": missing_fields,
        "enrichment_instruction": (
            f"Följande kärnfält saknas och ska enrichas: {missing_fields}"
        ),
    }
