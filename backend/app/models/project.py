"""
EWC Compute — Project Pydantic models.

A Project is the workspace container. Every engineering object in the platform
(twins, templates, sim runs, dashboards, audit events) belongs to a Project.

Access control rule: every query for sub-objects (twins, templates, etc.) must
include project_id AND (user_id or org_id). Ownership is checked at the Project
level; sub-objects inherit it. A user who does not own or share a project must
never be able to read or write its contents — enforce at query level.

Collections:
  projects — one document per project
"""
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from beanie import Document, Indexed, Link
from pydantic import BaseModel, Field

from app.models.user import User


# ── Enums ─────────────────────────────────────────────────────────────────

class ProjectStatus(StrEnum):
    """
    Lifecycle states of a project.

    active    — normal working state; all operations permitted
    archived  — read-only; no new twins, templates, or sim runs
    deleted   — soft-deleted; hidden from lists; recovered within 30 days
    """
    ACTIVE   = "active"
    ARCHIVED = "archived"
    DELETED  = "deleted"


class SimulationDomain(StrEnum):
    """
    CAE simulation domain taxonomy from NVIDIA CAE canonical workflow.
    Used in Project domain_tags for filtering and in SimTemplate/SimRun.

    Source: https://www.nvidia.com/en-us/glossary/computer-aided-engineering/
    """
    CFD             = "cfd"             # Computational fluid dynamics
    FEM             = "fem"             # Finite element method — structural, thermal
    THERMAL         = "thermal"         # Standalone thermal analysis
    ELECTROMAGNETIC = "electromagnetic" # EM simulation (COMSOL, Lumerical)
    EDA             = "eda"             # Electronic design automation (Phase 3)
    COLLISION       = "collision"       # Explicit dynamics / crashworthiness (Phase 3)
    OPTICAL         = "optical"         # Photonics / optical simulation (Lumerical)


# ── Request / Response models ─────────────────────────────────────────────

class ProjectCreate(BaseModel):
    """POST /projects request body."""
    name: Annotated[str, Field(min_length=1, max_length=120)]
    description: Annotated[str, Field(max_length=1000)] = ""
    domain_tags: list[SimulationDomain] = Field(
        default_factory=list,
        description="Simulation domains this project will work with. "
                    "Used for filtering and template suggestions.",
    )


class ProjectUpdate(BaseModel):
    """PATCH /projects/{id} — partial update."""
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    description: Annotated[str, Field(max_length=1000)] | None = None
    domain_tags: list[SimulationDomain] | None = None
    status: ProjectStatus | None = None


class ProjectPublic(BaseModel):
    """Project representation returned in API responses."""
    id: str
    name: str
    description: str
    status: ProjectStatus
    domain_tags: list[SimulationDomain]
    owner_id: str
    org_id: str | None
    twin_count: int
    template_count: int
    created_at: datetime
    updated_at: datetime


class ProjectSummary(BaseModel):
    """Compact representation for list views."""
    id: str
    name: str
    status: ProjectStatus
    domain_tags: list[SimulationDomain]
    twin_count: int
    updated_at: datetime


# ── Database document ─────────────────────────────────────────────────────

class Project(Document):
    """
    MongoDB document. Stored in the 'projects' collection.

    Ownership:
      - owner_id: the creating User (always set)
      - org_id:   set for Team/Enterprise projects; None for individual tier

    Sub-object counts (twin_count, template_count) are denormalised here
    for efficient list-view rendering — updated atomically on each create/delete.
    """
    name: Annotated[str, Indexed()]
    description: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    domain_tags: list[SimulationDomain] = Field(default_factory=list)

    # Ownership — both indexed for access control queries
    owner_id: Annotated[str, Indexed()]   # User.id as string
    org_id: Annotated[str | None, Indexed()] = None

    # Denormalised counters — incremented/decremented by services
    twin_count: int = 0
    template_count: int = 0

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "projects"
        indexes = [
            "owner_id",
            "org_id",
            [("owner_id", 1), ("status", 1)],    # Compound: list active projects by owner
            [("org_id",   1), ("status", 1)],    # Compound: list active projects by org
        ]

    def to_public(self) -> ProjectPublic:
        return ProjectPublic(
            id=str(self.id),
            name=self.name,
            description=self.description,
            status=self.status,
            domain_tags=self.domain_tags,
            owner_id=self.owner_id,
            org_id=self.org_id,
            twin_count=self.twin_count,
            template_count=self.template_count,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def to_summary(self) -> ProjectSummary:
        return ProjectSummary(
            id=str(self.id),
            name=self.name,
            status=self.status,
            domain_tags=self.domain_tags,
            twin_count=self.twin_count,
            updated_at=self.updated_at,
        )
