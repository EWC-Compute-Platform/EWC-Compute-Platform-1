"""
assistant_service.py
────────────────────────────────────────────────────────────────────────────────
Physical AI Assistant — DSR-CRAG pipeline
EWC Compute Platform · backend/app/services/assistant_service.py

Architecture
────────────
DSR-CRAG = Dual-State Corrective Retrieval-Augmented Generation

  State 1 — Primary retrieval
    embed(query) → Atlas vector search → score chunks → if quality OK → proceed

  State 2 — Corrective re-retrieval (triggered when State 1 quality is low)
    reformulate_query(query, low-quality chunks) → re-embed → second Atlas search
    → merge and re-rank results → proceed

  Generation
    format_context(chunks) → query(NIM) → validate_response(answer)
    → attach_provenance(answer, chunks) → return AssistantResponse

Corpus chunk document schema (MongoDB collection: ewc_engineering_corpus)
────────────────────────────────────────────────────────────────────────────────
{
  "_id":             ObjectId,
  "chunk_id":        str,           # UUID, stable identifier
  "source":          str,           # e.g. "ASHRAE Handbook 2021, Chapter 3"
  "title":           str,           # Document / section title
  "domain":          str,           # cfd|fem|thermal|electromagnetic|eda|
                                    # optical|materials|general
  "chunk_text":      str,           # Raw text of this chunk
  "embedding":       [float],       # 1024-dim nv-embedqa-e5-v5 vector
  "page_number":     int | None,
  "section":         str | None,    # Section heading within source
  "confidence_tier": str,           # authoritative|reference|model_estimate
  "created_at":      datetime,
  "metadata":        dict           # Arbitrary extra fields (DOI, URL, etc.)
}

Atlas vector search index name: ewc_engineering_corpus
Vector field: embedding
Dimensions: 1024
Similarity: cosine
────────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from openai import AsyncOpenAI
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

CORPUS_COLLECTION = "ewc_engineering_corpus"
VECTOR_SEARCH_INDEX = settings.VECTOR_SEARCH_INDEX   # "ewc_engineering_corpus"
EMBEDDING_DIMENSIONS = 1024                           # nv-embedqa-e5-v5
TOP_K_PRIMARY = 8          # chunks retrieved in State 1
TOP_K_CORRECTIVE = 6       # additional chunks retrieved in State 2
RELEVANCE_THRESHOLD = 0.72 # cosine similarity floor; below → trigger State 2
MIN_QUALITY_CHUNKS = 3     # minimum chunks above threshold to skip State 2
MAX_CONTEXT_CHARS = 6000   # hard cap on context sent to NIM

ENGINEERING_SYSTEM_PROMPT = """\
You are the EWC Compute Physical AI Assistant — an engineering-domain copilot \
grounded in a curated technical corpus. Your role is to give precise, \
trustworthy answers to engineering and simulation questions.

Rules you must always follow:
1. Every specific numeric value, formula, or physical constant you state must \
   be tagged with its provenance: either "retrieved from [source]" if it came \
   from the retrieved context, or "model estimate — verify before use" if it \
   did not.
2. If the retrieved context does not contain enough information to answer \
   confidently, say so explicitly. Never fabricate data.
3. Keep answers concise and technically precise. Use SI units unless the \
   context specifies otherwise.
4. Do not suggest platform actions (running simulations, modifying twins, etc.) \
   — those require explicit engineer confirmation through the confirmation gate.
"""

REFORMULATION_PROMPT = """\
The following engineering query returned low-relevance retrieval results. \
Reformulate it as a more specific, terminology-rich query that will retrieve \
better corpus matches. Return only the reformulated query — no explanation.

Original query: {query}
Low-relevance snippets: {snippets}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────────────────────

class CorpusChunk(BaseModel):
    """A single retrieved chunk from the engineering corpus."""
    chunk_id: str
    source: str
    title: str
    domain: str
    chunk_text: str
    page_number: int | None = None
    section: str | None = None
    confidence_tier: str = "reference"   # authoritative | reference | model_estimate
    similarity_score: float = 0.0        # populated after vector search
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProvenanceTag(BaseModel):
    """Provenance record attached to a specific claim in the response."""
    claim_index: int          # Position of the claim in the response (0-based)
    source: str               # e.g. "ASHRAE Handbook 2021, Chapter 3"
    confidence: str           # high | moderate | low | model_estimate
    chunk_id: str
    similarity_score: float


class AssistantRequest(BaseModel):
    """Incoming request to the assistant service."""
    query: str = Field(..., min_length=1, max_length=2000)
    project_id: str | None = None    # Optional project scope for future filtering
    domain_hint: str | None = None   # Optional domain hint (cfd|fem|thermal|…)
    conversation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    turn_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class AssistantResponse(BaseModel):
    """Full response returned by the assistant service."""
    conversation_id: str
    turn_id: str
    answer: str
    provenance: list[ProvenanceTag]
    retrieval_state: str          # "primary" | "corrective" | "fallback"
    chunks_used: int
    model: str
    latency_ms: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RetrievalResult(BaseModel):
    """Internal result from a single retrieval pass."""
    chunks: list[CorpusChunk]
    mean_similarity: float
    quality_pass: bool   # True if mean_similarity >= RELEVANCE_THRESHOLD


# ─────────────────────────────────────────────────────────────────────────────
# NIM client (module-level singleton — shared across requests)
# ─────────────────────────────────────────────────────────────────────────────

_nim_client: AsyncOpenAI | None = None


def _get_nim_client() -> AsyncOpenAI:
    """Return (or lazily initialise) the NIM AsyncOpenAI client."""
    global _nim_client
    if _nim_client is None:
        _nim_client = AsyncOpenAI(
            base_url=settings.NIM_BASE_URL,
            api_key=settings.NIM_API_KEY,
            http_client=httpx.AsyncClient(timeout=60.0),
        )
    return _nim_client


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Embed
# ─────────────────────────────────────────────────────────────────────────────

async def embed(text: str) -> list[float]:
    """
    Embed a text string using NVIDIA NIM nv-embedqa-e5-v5.

    Returns a 1024-dimensional float vector.
    Raises httpx.HTTPStatusError on NIM API failure.
    """
    client = _get_nim_client()
    response = await client.embeddings.create(
        model=settings.NIM_EMBEDDING_MODEL,   # nvidia/nv-embedqa-e5-v5
        input=text,
        encoding_format="float",
        extra_body={"input_type": "query"},   # NIM-specific: "query" vs "passage"
    )
    vector = response.data[0].embedding
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Unexpected embedding dimension: got {len(vector)}, "
            f"expected {EMBEDDING_DIMENSIONS}"
        )
    return vector


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Retrieve (Atlas vector search)
# ─────────────────────────────────────────────────────────────────────────────

async def _vector_search(
    db: AsyncIOMotorDatabase,
    query_vector: list[float],
    top_k: int,
    domain_filter: str | None = None,
) -> list[CorpusChunk]:
    """
    Run a MongoDB Atlas vector search against the engineering corpus.

    Pipeline stages:
      $vectorSearch → $project (add score) → optional $match (domain filter)

    Atlas index configuration expected:
      index name : ewc_engineering_corpus
      field      : embedding
      dimensions : 1024
      similarity : cosine
      type       : knnVector
    """
    pipeline: list[dict[str, Any]] = [
        {
            "$vectorSearch": {
                "index": VECTOR_SEARCH_INDEX,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": top_k * 10,   # over-fetch for filtering
                "limit": top_k,
            }
        },
        {
            "$project": {
                "chunk_id": 1,
                "source": 1,
                "title": 1,
                "domain": 1,
                "chunk_text": 1,
                "page_number": 1,
                "section": 1,
                "confidence_tier": 1,
                "metadata": 1,
                "similarity_score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    if domain_filter:
        pipeline.append({"$match": {"domain": domain_filter}})

    collection = db[CORPUS_COLLECTION]
    cursor = collection.aggregate(pipeline)

    chunks: list[CorpusChunk] = []
    async for doc in cursor:
        doc.pop("_id", None)
        chunks.append(CorpusChunk(**doc))

    return chunks


def _score_retrieval(chunks: list[CorpusChunk]) -> RetrievalResult:
    """
    Evaluate the quality of a retrieval pass.

    Quality passes when the mean cosine similarity of the top-k chunks
    exceeds RELEVANCE_THRESHOLD AND at least MIN_QUALITY_CHUNKS chunks
    are above the threshold individually.
    """
    if not chunks:
        return RetrievalResult(chunks=[], mean_similarity=0.0, quality_pass=False)

    scores = [c.similarity_score for c in chunks]
    mean_sim = sum(scores) / len(scores)
    above_threshold = sum(1 for s in scores if s >= RELEVANCE_THRESHOLD)
    quality_pass = (
        mean_sim >= RELEVANCE_THRESHOLD and above_threshold >= MIN_QUALITY_CHUNKS
    )

    return RetrievalResult(
        chunks=chunks,
        mean_similarity=round(mean_sim, 4),
        quality_pass=quality_pass,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Corrective re-retrieval (DSR State 2)
# ─────────────────────────────────────────────────────────────────────────────

async def _reformulate_query(
    original_query: str,
    low_quality_chunks: list[CorpusChunk],
) -> str:
    """
    Use NIM to produce a more specific, corpus-aligned reformulation
    of a query that returned poor retrieval results.
    """
    client = _get_nim_client()
    snippets = " | ".join(
        c.chunk_text[:120] for c in low_quality_chunks[:3]
    )
    prompt = REFORMULATION_PROMPT.format(
        query=original_query,
        snippets=snippets,
    )
    response = await client.chat.completions.create(
        model=settings.NIM_MODEL_ENGINEERING,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=128,
    )
    reformulated = response.choices[0].message.content.strip()
    logger.info(
        "DSR corrective reformulation",
        extra={"original": original_query, "reformulated": reformulated},
    )
    return reformulated


async def _corrective_retrieve(
    db: AsyncIOMotorDatabase,
    original_query: str,
    state1_chunks: list[CorpusChunk],
    domain_hint: str | None,
) -> tuple[list[CorpusChunk], str]:
    """
    DSR State 2: reformulate the query, re-embed, search again,
    and merge with the best State 1 chunks.

    Returns (merged_chunks, retrieval_state_label).
    """
    reformulated = await _reformulate_query(original_query, state1_chunks)
    corrective_vector = await embed(reformulated)
    corrective_chunks = await _vector_search(
        db, corrective_vector, TOP_K_CORRECTIVE, domain_hint
    )

    # Merge: keep top-3 from State 1 + all State 2 results, deduplicate by chunk_id
    seen: set[str] = set()
    merged: list[CorpusChunk] = []
    for chunk in sorted(state1_chunks, key=lambda c: c.similarity_score, reverse=True)[:3]:
        if chunk.chunk_id not in seen:
            seen.add(chunk.chunk_id)
            merged.append(chunk)
    for chunk in corrective_chunks:
        if chunk.chunk_id not in seen:
            seen.add(chunk.chunk_id)
            merged.append(chunk)

    merged.sort(key=lambda c: c.similarity_score, reverse=True)
    return merged, "corrective"


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Format context
# ─────────────────────────────────────────────────────────────────────────────

def _format_context(chunks: list[CorpusChunk]) -> str:
    """
    Serialise retrieved chunks into a structured context block for NIM.

    Each chunk is labelled with its source and confidence tier so the model
    can generate accurate provenance tags in its response.
    Character budget is capped at MAX_CONTEXT_CHARS.
    """
    parts: list[str] = []
    total_chars = 0

    for i, chunk in enumerate(chunks):
        header = (
            f"[CHUNK {i + 1}] "
            f"Source: {chunk.source} | "
            f"Domain: {chunk.domain} | "
            f"Confidence: {chunk.confidence_tier}"
        )
        if chunk.section:
            header += f" | Section: {chunk.section}"
        block = f"{header}\n{chunk.chunk_text}"

        if total_chars + len(block) > MAX_CONTEXT_CHARS:
            break

        parts.append(block)
        total_chars += len(block)

    return "\n\n---\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Query NIM
# ─────────────────────────────────────────────────────────────────────────────

async def query(prompt: str, context: str) -> str:
    """
    Send the user query and formatted retrieval context to NIM for inference.

    Uses Nemotron-4-340B-Instruct at temperature=0.1 (deterministic engineering
    responses). Returns the raw assistant message content.
    """
    client = _get_nim_client()
    response = await client.chat.completions.create(
        model=settings.NIM_MODEL_ENGINEERING,   # nvidia/nemotron-4-340b-instruct
        messages=[
            {"role": "system", "content": ENGINEERING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Retrieved context:\n\n{context}\n\n"
                    f"────────────────────────────────\n\n"
                    f"Engineer's query: {prompt}"
                ),
            },
        ],
        temperature=0.1,
        max_tokens=1024,
    )
    return response.choices[0].message.content


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — Validate and attach provenance
# ─────────────────────────────────────────────────────────────────────────────

_NUMERIC_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?(?:\s*[×x]\s*10[⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+)?"  # plain or scientific
    r"(?:\s*(?:Pa|MPa|GPa|K|°C|W|kW|MW|J|kJ|m|mm|kg|g|s|Hz|kHz|MHz|GHz|"
    r"rad|deg|N|kN|MN|A|V|Ω|T|F|H|mol|cd|lm|lx|Wb|S|m²|m³|m/s|m/s²))?"
    r"\b"
)


def _validate_response(answer: str) -> list[str]:
    """
    Check the NIM response for numeric claims that lack provenance tags.

    Returns a list of untagged numeric strings that may need manual review.
    This does not block the response — it populates a warning field used
    by the API layer for logging and QA.
    """
    numbers_found = _NUMERIC_PATTERN.findall(answer)
    untagged: list[str] = []

    for number in numbers_found:
        # A number is "tagged" if "retrieved from" or "model estimate" appears
        # within ~200 chars of it in the answer text
        idx = answer.find(number)
        window = answer[max(0, idx - 200): idx + 200].lower()
        if "retrieved from" not in window and "model estimate" not in window:
            untagged.append(number)

    return list(set(untagged))


def _build_provenance(
    answer: str,
    chunks: list[CorpusChunk],
) -> list[ProvenanceTag]:
    """
    Build a structured provenance list by correlating chunk source mentions
    in the answer text with the retrieved corpus chunks.

    Each ProvenanceTag links a claim position in the answer to its source chunk.
    """
    provenance: list[ProvenanceTag] = []
    claim_index = 0

    for chunk in chunks:
        # Look for explicit mentions of the source in the answer
        source_lower = chunk.source.lower()
        answer_lower = answer.lower()

        if source_lower in answer_lower or f"chunk {chunks.index(chunk) + 1}" in answer_lower:
            confidence = _tier_to_confidence(chunk.confidence_tier, chunk.similarity_score)
            provenance.append(
                ProvenanceTag(
                    claim_index=claim_index,
                    source=chunk.source,
                    confidence=confidence,
                    chunk_id=chunk.chunk_id,
                    similarity_score=chunk.similarity_score,
                )
            )
            claim_index += 1

    # If no explicit source mentions found, still tag the top-3 chunks
    # as implicit provenance so the caller always has audit trail
    if not provenance:
        for i, chunk in enumerate(chunks[:3]):
            confidence = _tier_to_confidence(chunk.confidence_tier, chunk.similarity_score)
            provenance.append(
                ProvenanceTag(
                    claim_index=i,
                    source=chunk.source,
                    confidence=confidence,
                    chunk_id=chunk.chunk_id,
                    similarity_score=chunk.similarity_score,
                )
            )

    return provenance


def _tier_to_confidence(tier: str, similarity: float) -> str:
    """Map confidence_tier + similarity score to a human-readable confidence label."""
    if tier == "authoritative" and similarity >= 0.85:
        return "high"
    if tier == "authoritative" and similarity >= RELEVANCE_THRESHOLD:
        return "moderate"
    if tier == "reference" and similarity >= 0.80:
        return "moderate"
    if tier == "model_estimate":
        return "model_estimate — verify before use"
    return "low"


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline — run_assistant
# ─────────────────────────────────────────────────────────────────────────────

async def run_assistant(
    request: AssistantRequest,
    db: AsyncIOMotorDatabase,
) -> AssistantResponse:
    """
    Execute the full DSR-CRAG pipeline for a single assistant turn.

    Stages:
      1. Embed query                      → query_vector
      2. State 1: primary vector search   → state1_result
      3. Quality gate
         pass  → proceed with state1_result.chunks
         fail  → State 2: corrective re-retrieval → merged_chunks
      4. Format context
      5. Query NIM                        → raw_answer
      6. Validate response
      7. Build provenance tags
      8. Return AssistantResponse
    """
    import time
    t_start = time.perf_counter()

    logger.info(
        "assistant_pipeline_start",
        extra={
            "conversation_id": request.conversation_id,
            "turn_id": request.turn_id,
            "query_length": len(request.query),
        },
    )

    # ── 1. Embed ──────────────────────────────────────────────────────────────
    query_vector = await embed(request.query)

    # ── 2. State 1: primary retrieval ─────────────────────────────────────────
    state1_chunks = await _vector_search(
        db, query_vector, TOP_K_PRIMARY, request.domain_hint
    )
    state1_result = _score_retrieval(state1_chunks)

    logger.info(
        "state1_retrieval",
        extra={
            "chunks": len(state1_chunks),
            "mean_similarity": state1_result.mean_similarity,
            "quality_pass": state1_result.quality_pass,
        },
    )

    # ── 3. Quality gate → State 2 if needed ───────────────────────────────────
    retrieval_state: str
    final_chunks: list[CorpusChunk]

    if state1_result.quality_pass:
        final_chunks = state1_result.chunks
        retrieval_state = "primary"
    elif not state1_chunks:
        # No results at all — fallback to generation-only with explicit warning
        final_chunks = []
        retrieval_state = "fallback"
        logger.warning(
            "empty_retrieval_fallback",
            extra={"conversation_id": request.conversation_id},
        )
    else:
        final_chunks, retrieval_state = await _corrective_retrieve(
            db, request.query, state1_chunks, request.domain_hint
        )
        logger.info(
            "state2_corrective_retrieval",
            extra={"final_chunks": len(final_chunks)},
        )

    # ── 4. Format context ─────────────────────────────────────────────────────
    context = _format_context(final_chunks) if final_chunks else (
        "No relevant corpus chunks retrieved. Answer from model knowledge only. "
        "All numeric values must be tagged as 'model estimate — verify before use'."
    )

    # ── 5. Query NIM ──────────────────────────────────────────────────────────
    raw_answer = await query(request.query, context)

    # ── 6. Validate response ──────────────────────────────────────────────────
    untagged_numerics = _validate_response(raw_answer)
    if untagged_numerics:
        logger.warning(
            "untagged_numeric_claims_detected",
            extra={
                "turn_id": request.turn_id,
                "untagged": untagged_numerics,
            },
        )

    # ── 7. Build provenance ───────────────────────────────────────────────────
    provenance = _build_provenance(raw_answer, final_chunks)

    # ── 8. Assemble response ──────────────────────────────────────────────────
    latency_ms = (time.perf_counter() - t_start) * 1000

    logger.info(
        "assistant_pipeline_complete",
        extra={
            "turn_id": request.turn_id,
            "retrieval_state": retrieval_state,
            "chunks_used": len(final_chunks),
            "latency_ms": round(latency_ms, 1),
            "untagged_numerics": len(untagged_numerics),
        },
    )

    return AssistantResponse(
        conversation_id=request.conversation_id,
        turn_id=request.turn_id,
        answer=raw_answer,
        provenance=provenance,
        retrieval_state=retrieval_state,
        chunks_used=len(final_chunks),
        model=settings.NIM_MODEL_ENGINEERING,
        latency_ms=round(latency_ms, 1),
    )


