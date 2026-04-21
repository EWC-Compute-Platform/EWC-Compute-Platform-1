"""
assistant.py
────────────────────────────────────────────────────────────────────────────────
Physical AI Assistant — FastAPI router
EWC Compute Platform · backend/app/api/v1/assistant.py

Architectural role
──────────────────
This module is the HTTP boundary of the Physical AI Assistant. It exposes
the DSR-CRAG pipeline and the confirmation gate as a coherent REST API.

It does three things, and only three things:

  1. Receives HTTP requests, validates them, injects dependencies
  2. Calls the service layer (assistant_service, confirmation_gate)
  3. Returns typed HTTP responses

No business logic lives here. No pipeline logic. No gate logic.
The router is a thin translation layer between HTTP and the service layer.

Endpoint map
────────────
  POST   /v1/assistant/query                    Run DSR-CRAG pipeline
  GET    /v1/assistant/proposals                List pending proposals
  POST   /v1/assistant/proposals/{id}/confirm   Confirm a proposal
  POST   /v1/assistant/proposals/{id}/execute   Execute a confirmed proposal
  POST   /v1/assistant/proposals/{id}/abort     Abort a proposal
  GET    /v1/assistant/history                  Conversation history (Phase 2 stub)

Action detection
────────────────
When the DSR-CRAG pipeline generates a response that contains an action
proposal (detectable by the confirmation-request pattern defined in
ACTIVE_SYSTEM_PROMPT), the query endpoint automatically calls
confirmation_gate.propose() and attaches the resulting ProposalSummary
to the query response. The client can then surface the confirm/abort UI.

Action detection uses a two-step approach:
  Step 1: Lightweight keyword scan for the confirmation pattern
          (fast, no NIM call, catches ~95% of cases)
  Step 2: If Step 1 fires, a structured NIM extraction call parses
          action_type and parameters from the proposal text
          (ensures the handler gets clean, typed parameters)

Assumptions about Phase 0 infrastructure
─────────────────────────────────────────
  - get_database()    : core/database.py → AsyncIOMotorDatabase
  - get_current_user(): core/security.py → User (with .user_id: str)
  - User model        : models/user.py   → has user_id, email, role fields
  - APIRouter prefix "/assistant" registered in main.py under "/v1"
────────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.agents.confirmation_gate import (
    ActionProposal,
    ActionType,
    ProposalSummary,
    abort,
    confirm,
    execute,
    list_pending,
    propose,
)
from app.core.config import settings
from app.core.database import get_database
from app.core.security import get_current_user
from app.models.user import User
from app.services.assistant_service import (
    AssistantRequest,
    AssistantResponse,
    run_assistant,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / response schemas (router-layer only)
# ─────────────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """
    Incoming query from the engineer's chat interface.

    conversation_id is generated client-side and held across turns
    so the full conversation thread is traceable in the audit log.
    domain_hint is optional — when provided it narrows the Atlas
    vector search to a single simulation domain, improving retrieval
    precision for domain-specific queries.
    """
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    domain_hint: str | None = None   # cfd|fem|thermal|electromagnetic|
                                      # eda|optical|materials|general
    project_id: str | None = None


class QueryResponse(BaseModel):
    """
    Full response returned by the query endpoint.

    assistant_response carries the DSR-CRAG answer with provenance.
    proposal is set when the assistant's answer contains an action
    proposal — the client should surface the confirm/abort UI when
    this field is non-null.
    """
    assistant_response: AssistantResponse
    proposal: ProposalSummary | None = None


class ConfirmRequest(BaseModel):
    """Body for the confirm endpoint — currently minimal, extensible for
    Phase 2 delegation (confirmed_by may differ from the original requester)."""
    note: str | None = None   # Optional engineer note stored with confirmation


class AbortRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class HistoryEntry(BaseModel):
    """Single turn in the conversation history. Phase 2 stub."""
    turn_id: str
    conversation_id: str
    query: str
    answer: str
    retrieval_state: str
    created_at: str


# ─────────────────────────────────────────────────────────────────────────────
# Action detection helpers
# ─────────────────────────────────────────────────────────────────────────────

# Pattern from ACTIVE_SYSTEM_PROMPT_V1 — the assistant closes every
# action proposal with a confirmation request in this form.
_CONFIRMATION_PATTERN = re.compile(
    r"shall i proceed|do you want me to proceed|confirm to proceed|"
    r"would you like me to|please confirm|awaiting your confirmation",
    re.IGNORECASE,
)

# Maps keywords in the assistant's proposal text to ActionType values.
# Order matters — more specific patterns first.
_ACTION_TYPE_HINTS: list[tuple[re.Pattern[str], ActionType]] = [
    (re.compile(r"dispatch|run|submit|simulation|cfd|fem|flow360|comsol", re.I),
     ActionType.SIM_DISPATCH),
    (re.compile(r"export|fabricat|gdsii|stl|step|iges", re.I),
     ActionType.EXPORT_GEOMETRY),
    (re.compile(r"template|update.*template|modify.*template", re.I),
     ActionType.TEMPLATE_UPDATE),
    (re.compile(r"twin|modify.*twin|update.*twin", re.I),
     ActionType.TWIN_MODIFY),
    (re.compile(r"corpus|ingest|add.*document|add.*source", re.I),
     ActionType.CORPUS_INGEST),
]

# NIM client — reuse the same singleton from assistant_service
_nim_client: AsyncOpenAI | None = None


def _get_nim_client() -> AsyncOpenAI:
    global _nim_client
    if _nim_client is None:
        _nim_client = AsyncOpenAI(
            base_url=settings.NIM_BASE_URL,
            api_key=settings.NIM_API_KEY,
            http_client=httpx.AsyncClient(timeout=30.0),
        )
    return _nim_client


def _contains_action_proposal(answer: str) -> bool:
    """
    Step 1: fast keyword scan.
    Returns True if the assistant's answer contains a confirmation request,
    indicating it has proposed a platform action.
    """
    return bool(_CONFIRMATION_PATTERN.search(answer))


def _detect_action_type(answer: str) -> ActionType:
    """
    Infer the ActionType from the assistant's proposal text using
    keyword matching. Falls back to SIM_DISPATCH as the most common
    Phase 1 action if no pattern matches.
    """
    for pattern, action_type in _ACTION_TYPE_HINTS:
        if pattern.search(answer):
            return action_type
    return ActionType.SIM_DISPATCH


async def _extract_proposal_parameters(
    answer: str,
    action_type: ActionType,
) -> dict[str, Any]:
    """
    Step 2: structured NIM extraction call.

    When Step 1 confirms an action proposal is present, this call
    asks NIM to extract the action parameters as JSON. Using NIM
    itself for extraction ensures the parameters are interpreted
    in the same engineering domain context as the original answer.

    Returns a dict of extracted parameters, or a fallback dict
    containing the raw answer text if extraction fails — ensuring
    the proposal is always created even if structured extraction
    cannot be completed.
    """
    if not settings.nim_available:
        return {"raw_proposal": answer, "action_type": action_type}

    client = _get_nim_client()
    extraction_prompt = (
        f"The following is a Physical AI Assistant response that proposes "
        f"a {action_type} action. Extract the action parameters as a JSON "
        f"object. Include only concrete parameters (model names, file paths, "
        f"numerical values, solver settings) — not conversational text. "
        f"Return only valid JSON, no explanation.\n\n"
        f"Response:\n{answer}"
    )

    try:
        response = await client.chat.completions.create(
            model=settings.NIM_MODEL_ENGINEERING,
            messages=[{"role": "user", "content": extraction_prompt}],
            temperature=0.0,
            max_tokens=256,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE)
        return json.loads(raw)
    except Exception as exc:
        logger.warning(
            "action_parameter_extraction_failed | action=%s error=%s",
            action_type, exc,
        )
        return {"raw_proposal": answer, "action_type": action_type}


async def _maybe_propose(
    answer: str,
    user_id: str,
    project_id: str | None,
    db: AsyncIOMotorDatabase,
) -> ProposalSummary | None:
    """
    Orchestrate the two-step action detection and, if an action is
    detected, create a proposal via the confirmation gate.

    Returns a ProposalSummary if a proposal was created, None otherwise.
    Failures in detection or proposal creation are logged and swallowed —
    the query response is always returned even if proposal creation fails.
    """
    if not _contains_action_proposal(answer):
        return None

    try:
        action_type = _detect_action_type(answer)
        parameters = await _extract_proposal_parameters(answer, action_type)

        # Use the full answer as the description — it IS the plain-language
        # proposal the engineer should read before confirming.
        # Truncate to 1000 chars for the summary; full text is in parameters.
        description = answer[:1000] + ("…" if len(answer) > 1000 else "")

        proposal = await propose(
            action_type=action_type,
            description=description,
            parameters=parameters,
            requested_by=user_id,
            db=db,
            project_id=project_id,
        )

        return ProposalSummary(
            proposal_id=proposal.proposal_id,
            action_type=proposal.action_type,
            description=proposal.description,
            status=proposal.status,
            created_at=proposal.created_at,
            expires_at=proposal.expires_at,
        )

    except Exception as exc:
        logger.error(
            "proposal_creation_failed | user=%s error=%s", user_id, exc
        )
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit a query to the Physical AI Assistant",
    description=(
        "Runs the DSR-CRAG pipeline: embed → retrieve → (corrective retrieve) "
        "→ NIM inference → provenance tagging. "
        "If the response contains an action proposal, a confirmation gate "
        "proposal is automatically created and returned in the `proposal` field."
    ),
)
async def query_assistant(
    body: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> QueryResponse:
    """
    Main assistant query endpoint.

    The client submits a natural language engineering query. The full
    DSR-CRAG pipeline runs and returns a grounded, provenance-tagged answer.

    If the assistant determines that an action should be proposed (e.g.
    dispatching a simulation), the response also contains a `proposal`
    object. The client surfaces the confirm/abort UI when this is non-null.
    The engineer must explicitly POST to /proposals/{id}/confirm to
    proceed — the action is never triggered by this endpoint alone.
    """
    if not settings.nim_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "NIM API key is not configured. "
                "Set NIM_API_KEY in .env to enable the Physical AI Assistant."
            ),
        )

    request = AssistantRequest(
        query=body.query,
        conversation_id=body.conversation_id,
        domain_hint=body.domain_hint,
        project_id=body.project_id,
    )

    try:
        assistant_response = await run_assistant(request, db)
    except Exception as exc:
        logger.error(
            "assistant_query_failed | user=%s conversation=%s error=%s",
            current_user.user_id,
            body.conversation_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Assistant pipeline failed: {exc}",
        )

    # Detect and create proposal if the assistant proposed an action
    proposal = await _maybe_propose(
        answer=assistant_response.answer,
        user_id=current_user.user_id,
        project_id=body.project_id,
        db=db,
    )

    return QueryResponse(
        assistant_response=assistant_response,
        proposal=proposal,
    )


@router.get(
    "/proposals",
    response_model=list[ProposalSummary],
    status_code=status.HTTP_200_OK,
    summary="List pending proposals for the current engineer",
    description=(
        "Returns all PENDING proposals awaiting confirmation. "
        "Expired proposals are cleaned up lazily on read."
    ),
)
async def get_proposals(
    project_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[ProposalSummary]:
    """
    List all PENDING proposals for the current engineer.
    Used by the assistant UI to surface outstanding confirmations,
    including proposals from previous sessions that have not yet expired.
    """
    return await list_pending(
        user_id=current_user.user_id,
        db=db,
        project_id=project_id,
    )


@router.post(
    "/proposals/{proposal_id}/confirm",
    response_model=ProposalSummary,
    status_code=status.HTTP_200_OK,
    summary="Confirm a pending proposal",
    description=(
        "The explicit engineer confirmation. Transitions the proposal from "
        "PENDING to CONFIRMED. The proposal can then be executed or aborted. "
        "Proposals expire after 10 minutes if not confirmed."
    ),
)
async def confirm_proposal(
    proposal_id: str,
    body: ConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ProposalSummary:
    """
    This POST is the explicit human keystroke the architecture requires.

    It is deliberately a separate endpoint from execute() so that
    confirmation and execution are two distinct, auditable events.
    The engineer confirms they have reviewed the proposal; execution
    is a second step that can still be aborted between the two.
    """
    try:
        proposal = await confirm(
            proposal_id=proposal_id,
            confirmed_by=current_user.user_id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    logger.info(
        "proposal_confirmed_via_api | proposal_id=%s user=%s note=%r",
        proposal_id,
        current_user.user_id,
        body.note,
    )

    return ProposalSummary(
        proposal_id=proposal.proposal_id,
        action_type=proposal.action_type,
        description=proposal.description,
        status=proposal.status,
        created_at=proposal.created_at,
        expires_at=proposal.expires_at,
    )


@router.post(
    "/proposals/{proposal_id}/execute",
    response_model=ProposalSummary,
    status_code=status.HTTP_200_OK,
    summary="Execute a confirmed proposal",
    description=(
        "Calls the registered action handler with the proposal's parameters. "
        "Requires the proposal to be in CONFIRMED status. "
        "On success, transitions to EXECUTED. "
        "On handler failure, stays CONFIRMED for retry or manual inspection."
    ),
)
async def execute_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ProposalSummary:
    """
    Execute a confirmed proposal.

    In practice the client calls confirm() and execute() in sequence
    when the engineer clicks the single "Confirm & Run" button. They
    are separate endpoints so each is individually auditable, and so
    a future Phase 2 flow can insert an approval step between them.
    """
    try:
        proposal = await execute(proposal_id=proposal_id, db=db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return ProposalSummary(
        proposal_id=proposal.proposal_id,
        action_type=proposal.action_type,
        description=proposal.description,
        status=proposal.status,
        created_at=proposal.created_at,
        expires_at=proposal.expires_at,
    )


@router.post(
    "/proposals/{proposal_id}/abort",
    response_model=ProposalSummary,
    status_code=status.HTTP_200_OK,
    summary="Abort a pending or confirmed proposal",
    description=(
        "Cancels the proposal before execution. Cannot abort an already "
        "EXECUTED proposal. The abort reason is stored in the audit record."
    ),
)
async def abort_proposal(
    proposal_id: str,
    body: AbortRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> ProposalSummary:
    try:
        proposal = await abort(
            proposal_id=proposal_id,
            aborted_by=current_user.user_id,
            reason=body.reason,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return ProposalSummary(
        proposal_id=proposal.proposal_id,
        action_type=proposal.action_type,
        description=proposal.description,
        status=proposal.status,
        created_at=proposal.created_at,
        expires_at=proposal.expires_at,
    )


@router.get(
    "/history",
    response_model=list[HistoryEntry],
    status_code=status.HTTP_200_OK,
    summary="Conversation history (Phase 2)",
    description=(
        "Returns the conversation history for the current engineer. "
        "Phase 1 stub — returns empty list. Full implementation in Phase 2 "
        "when assistant turns are persisted to MongoDB with conversation_id indexing."
    ),
)
async def get_history(
    conversation_id: str | None = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> list[HistoryEntry]:
    """
    Phase 2 stub. Returns empty list in Phase 1.

    Phase 2 implementation will:
    - Persist each AssistantResponse to ewc_assistant_history collection
    - Index by (user_id, conversation_id, created_at)
    - Return paginated turns filtered by conversation_id
    """
    logger.debug(
        "history_stub | user=%s conversation=%s",
        current_user.user_id,
        conversation_id,
    )
    return []



