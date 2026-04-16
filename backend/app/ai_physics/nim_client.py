"""
EWC Compute — NVIDIA NIM inference client.

Wraps the NVIDIA NIM API behind two clean async methods:
  query()  — send an engineering question, get a cited response
  embed()  — convert text to a 1024-dimensional vector for corpus retrieval

NIM exposes an OpenAI-compatible API, so the standard `openai` Python library
is used as the HTTP client. No NIM-specific SDK is required.

Authentication:
  Set NIM_API_KEY in .env
  Obtain from: build.nvidia.com → your account → API Keys

Models (configured in config.py):
  Inference:  nvidia/nemotron-4-340b-instruct  (NIM_MODEL_ENGINEERING)
  Embedding:  nvidia/nv-embedqa-e5-v5          (NIM_EMBEDDING_MODEL)
  Embedding dimensions: 1024 (must match Atlas Vector Search index)

Phase guard:
  This module is active from Phase 1.
  In Phase 0, NIM_API_KEY is empty and nim_available() returns False.
  All callers check nim_available() before calling query() or embed().
"""
import asyncio
from typing import AsyncIterator

import structlog
from openai import AsyncOpenAI, APIConnectionError, APIStatusError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.prompts import ACTIVE_SYSTEM_PROMPT, ACTIVE_PROMPT_VERSION

logger = structlog.get_logger(__name__)


# ── Client singleton ──────────────────────────────────────────────────────

def _build_client() -> AsyncOpenAI:
    """
    Build the AsyncOpenAI client pointed at NVIDIA NIM.
    NIM uses the same API surface as OpenAI — only the base_url changes.
    """
    return AsyncOpenAI(
        api_key=settings.NIM_API_KEY or "not-set",
        base_url=settings.NIM_BASE_URL,
        timeout=60.0,       # Engineering queries can be long; 60s is reasonable
        max_retries=0,      # Retries handled by tenacity below, not the client
    )


# Module-level client — created once, reused across requests
_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    """Return the NIM client, creating it on first call."""
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def nim_available() -> bool:
    """
    True when the NIM API key is configured.
    Phase gate: Phase 0 has no key; Phase 1 requires one.
    All callers should check this before invoking query() or embed().
    """
    return bool(settings.NIM_API_KEY)


# ── Health check ──────────────────────────────────────────────────────────

async def check_nim_health() -> dict[str, str]:
    """
    Verify NIM is reachable and the models are available.
    Called at Phase 1 startup. Returns a status dict for the health endpoint.
    """
    if not nim_available():
        return {
            "status": "unavailable",
            "reason": "NIM_API_KEY not configured — Phase 1 not active",
        }
    try:
        client = get_client()
        # List available models — lightweight check, no token cost
        models = await client.models.list()
        model_ids = [m.id for m in models.data]
        inference_ok = settings.NIM_MODEL_ENGINEERING in model_ids
        embedding_ok = settings.NIM_EMBEDDING_MODEL in model_ids
        return {
            "status": "ok" if (inference_ok and embedding_ok) else "degraded",
            "inference_model": settings.NIM_MODEL_ENGINEERING,
            "embedding_model": settings.NIM_EMBEDDING_MODEL,
            "inference_available": str(inference_ok),
            "embedding_available": str(embedding_ok),
        }
    except Exception as exc:
        logger.warning("nim.health_check.failed", error=str(exc))
        return {"status": "unreachable", "reason": str(exc)}


# ── Core inference — query() ──────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type((APIConnectionError, RateLimitError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def query(
    user_message: str,
    retrieved_context: str = "",
    conversation_history: list[dict[str, str]] | None = None,
    temperature: float | None = None,
) -> str:
    """
    Send an engineering query to NVIDIA NIM and return the response text.

    Args:
        user_message:
            The engineer's question or request.
        retrieved_context:
            Pre-retrieved corpus chunks, formatted as a block of cited text.
            Assembled by assistant_service.py before this call.
            Empty string if no relevant corpus documents were found.
        conversation_history:
            Previous turns in the conversation, as a list of
            {"role": "user"|"assistant", "content": "..."} dicts.
            Pass None for a fresh query with no history.
        temperature:
            Override inference temperature. Defaults to settings value (0.1).
            Only override for specific routes that need different behaviour.

    Returns:
        The model's response as a plain string.
        The response will contain RETRIEVED/ESTIMATED citation markers
        as instructed by the system prompt.

    Raises:
        APIConnectionError: NIM endpoint unreachable (after retries)
        APIStatusError:     NIM returned a 4xx/5xx error
        RuntimeError:       NIM not configured (no API key)
    """
    if not nim_available():
        raise RuntimeError(
            "NIM API key not configured. "
            "Set NIM_API_KEY in .env to activate Phase 1."
        )

    # Build the message list
    # Order: system prompt → retrieved context (as system) → history → user query
    messages: list[dict[str, str]] = [
        {"role": "system", "content": ACTIVE_SYSTEM_PROMPT},
    ]

    if retrieved_context:
        messages.append({
            "role": "system",
            "content": (
                "The following documents were retrieved from the engineering corpus "
                "for this query. Use them as the primary source for your response. "
                "Cite each document you use with [Retrieved from: {title}].\n\n"
                f"{retrieved_context}"
            ),
        })

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": user_message})

    effective_temperature = (
        temperature
        if temperature is not None
        else settings.NIM_INFERENCE_TEMPERATURE
    )

    logger.info(
        "nim.query.start",
        model=settings.NIM_MODEL_ENGINEERING,
        prompt_version=ACTIVE_PROMPT_VERSION,
        has_context=bool(retrieved_context),
        history_turns=len(conversation_history) if conversation_history else 0,
        temperature=effective_temperature,
    )

    client = get_client()
    response = await client.chat.completions.create(
        model=settings.NIM_MODEL_ENGINEERING,
        messages=messages,                  # type: ignore[arg-type]
        temperature=effective_temperature,
        max_tokens=1024,
        stream=False,
    )

    result = response.choices[0].message.content or ""

    logger.info(
        "nim.query.complete",
        model=settings.NIM_MODEL_ENGINEERING,
        input_tokens=response.usage.prompt_tokens if response.usage else None,
        output_tokens=response.usage.completion_tokens if response.usage else None,
    )

    return result


# ── Streaming variant ─────────────────────────────────────────────────────

async def query_stream(
    user_message: str,
    retrieved_context: str = "",
) -> AsyncIterator[str]:
    """
    Streaming variant of query() — yields response text token by token.
    Used by the frontend chat interface for real-time display.
    Does not retry on failure — streaming retries are handled at the route level.

    Usage:
        async for chunk in nim_client.query_stream(message, context):
            yield chunk   # forward to SSE stream in the FastAPI route
    """
    if not nim_available():
        raise RuntimeError("NIM API key not configured.")

    messages: list[dict[str, str]] = [
        {"role": "system", "content": ACTIVE_SYSTEM_PROMPT},
    ]
    if retrieved_context:
        messages.append({
            "role": "system",
            "content": (
                "Retrieved corpus context:\n\n"
                f"{retrieved_context}"
            ),
        })
    messages.append({"role": "user", "content": user_message})

    client = get_client()
    stream = await client.chat.completions.create(
        model=settings.NIM_MODEL_ENGINEERING,
        messages=messages,              # type: ignore[arg-type]
        temperature=settings.NIM_INFERENCE_TEMPERATURE,
        max_tokens=1024,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


# ── Embedding ─────────────────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type((APIConnectionError, RateLimitError)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def embed(text: str) -> list[float]:
    """
    Convert text to a 1024-dimensional embedding vector.
    Used by assistant_service.py to embed engineer queries before
    performing vector search against the corpus in MongoDB Atlas.

    The embedding model (nvidia/nv-embedqa-e5-v5) produces 1024-dimensional
    vectors. The Atlas Vector Search index must be configured with the same
    dimensionality and cosine similarity metric.

    Args:
        text: The text to embed. Typically the engineer's query,
              optionally prefixed with a task instruction.

    Returns:
        A list of 1024 floats — the embedding vector.

    Raises:
        APIConnectionError: NIM endpoint unreachable (after retries)
        RuntimeError:       NIM not configured
    """
    if not nim_available():
        raise RuntimeError("NIM API key not configured.")

    # NIM embedding models accept an optional task instruction prefix
    # "query: " prefix is recommended for retrieval tasks with nv-embedqa-e5-v5
    prefixed_text = f"query: {text}"

    logger.info(
        "nim.embed.start",
        model=settings.NIM_EMBEDDING_MODEL,
        text_length=len(text),
    )

    client = get_client()
    response = await client.embeddings.create(
        model=settings.NIM_EMBEDDING_MODEL,
        input=prefixed_text,
        encoding_format="float",
    )

    vector = response.data[0].embedding

    logger.info(
        "nim.embed.complete",
        model=settings.NIM_EMBEDDING_MODEL,
        dimensions=len(vector),
    )

    return vector


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed multiple texts concurrently.
    Used by seed_corpus.py to batch-embed corpus documents at ingestion time.
    Runs up to 10 embeddings in parallel — NIM rate limits at higher concurrency.
    """
    semaphore = asyncio.Semaphore(10)

    async def _embed_one(text: str) -> list[float]:
        async with semaphore:
            return await embed(text)

    return await asyncio.gather(*[_embed_one(t) for t in texts])


