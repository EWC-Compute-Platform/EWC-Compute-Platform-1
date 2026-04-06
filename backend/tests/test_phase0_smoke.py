"""
EWC Compute — Phase 0 smoke tests.

These are the minimum tests that must pass before Phase 1 begins.
They prove the skeleton is wired correctly end to end:
  - Health endpoints respond
  - Auth cycle works (register → login → me → logout)
  - Project CRUD works
  - Twin creation works
  - Access control is enforced

Run: cd backend && pytest tests/test_phase0_smoke.py -v
"""
import pytest
from httpx import AsyncClient


# ── Health ─────────────────────────────────────────────────────────────────

async def test_health_live(app_client: AsyncClient) -> None:
    r = await app_client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_health_ready(app_client: AsyncClient) -> None:
    r = await app_client.get("/health/ready")
    # In test environment with mocks, both DB and Redis are healthy
    assert r.status_code == 200
    assert r.json()["ready"] is True


async def test_health_combined(app_client: AsyncClient) -> None:
    r = await app_client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data
    assert data["components"]["mongodb"]["status"] == "ok"
    assert data["components"]["redis"]["status"] == "ok"


# ── Auth — register ────────────────────────────────────────────────────────

async def test_register_success(app_client: AsyncClient) -> None:
    r = await app_client.post("/api/v1/auth/register", json={
        "email": "new@engineer.test",
        "password": "Secure1234",
        "full_name": "New Engineer",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "new@engineer.test"
    assert data["role"] == "individual"
    assert "hashed_password" not in data


async def test_register_duplicate_email(app_client: AsyncClient) -> None:
    payload = {"email": "dup@test.com", "password": "Test1234", "full_name": "Dup"}
    await app_client.post("/api/v1/auth/register", json=payload)
    r = await app_client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 409


async def test_register_weak_password(app_client: AsyncClient) -> None:
    r = await app_client.post("/api/v1/auth/register", json={
        "email": "weak@test.com",
        "password": "nodigits",
        "full_name": "Weak",
    })
    assert r.status_code == 422


# ── Auth — login ───────────────────────────────────────────────────────────

async def test_login_success(app_client: AsyncClient) -> None:
    await app_client.post("/api/v1/auth/register", json={
        "email": "login@test.com",
        "password": "Login1234",
        "full_name": "Login User",
    })
    r = await app_client.post("/api/v1/auth/login", json={
        "email": "login@test.com",
        "password": "Login1234",
    })
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(app_client: AsyncClient) -> None:
    await app_client.post("/api/v1/auth/register", json={
        "email": "badpass@test.com",
        "password": "Correct1234",
        "full_name": "Bad Pass",
    })
    r = await app_client.post("/api/v1/auth/login", json={
        "email": "badpass@test.com",
        "password": "Wrong1234",
    })
    assert r.status_code == 401


# ── Auth — me ──────────────────────────────────────────────────────────────

async def test_me_authenticated(
    app_client: AsyncClient, auth_headers: dict
) -> None:
    r = await app_client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "engineer@ewccompute.test"


async def test_me_unauthenticated(app_client: AsyncClient) -> None:
    r = await app_client.get("/api/v1/auth/me")
    assert r.status_code == 401


# ── Projects ───────────────────────────────────────────────────────────────

async def test_create_project(
    app_client: AsyncClient, auth_headers: dict
) -> None:
    r = await app_client.post(
        "/api/v1/projects",
        json={"name": "Wing Aero Study", "domain_tags": ["cfd"]},
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Wing Aero Study"
    assert "cfd" in data["domain_tags"]
    assert data["twin_count"] == 0


async def test_list_projects_empty(
    app_client: AsyncClient, auth_headers: dict
) -> None:
    r = await app_client.get("/api/v1/projects", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_get_project(
    app_client: AsyncClient, auth_headers: dict, test_project
) -> None:
    r = await app_client.get(
        f"/api/v1/projects/{test_project.id}",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["id"] == str(test_project.id)


async def test_get_project_not_found(
    app_client: AsyncClient, auth_headers: dict
) -> None:
    r = await app_client.get(
        "/api/v1/projects/000000000000000000000001",
        headers=auth_headers,
    )
    assert r.status_code == 404


async def test_project_access_control(
    app_client: AsyncClient, test_project, admin_headers: dict
) -> None:
    """Admin can access any project; other users cannot."""
    r = await app_client.get(
        f"/api/v1/projects/{test_project.id}",
        headers=admin_headers,
    )
    assert r.status_code == 200


# ── Twins ──────────────────────────────────────────────────────────────────

async def test_create_twin(
    app_client: AsyncClient, auth_headers: dict, test_project
) -> None:
    r = await app_client.post(
        f"/api/v1/projects/{test_project.id}/twins",
        json={
            "name": "ONERA M6 Wing",
            "domain": "cfd",
            "geometry_format": "step",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "ONERA M6 Wing"
    assert data["fidelity_level"] == "geometric"
    assert data["usd_stage_path"] is None   # Not yet exported


async def test_list_twins(
    app_client: AsyncClient, auth_headers: dict, test_project, test_twin
) -> None:
    r = await app_client.get(
        f"/api/v1/projects/{test_project.id}/twins",
        headers=auth_headers,
    )
    assert r.status_code == 200
    twins = r.json()
    assert len(twins) >= 1
    assert any(t["id"] == str(test_twin.id) for t in twins)


async def test_update_twin_upgrades_fidelity(
    app_client: AsyncClient, auth_headers: dict, test_project, test_twin
) -> None:
    """Setting material properties should auto-upgrade fidelity to behavioural."""
    r = await app_client.patch(
        f"/api/v1/projects/{test_project.id}/twins/{test_twin.id}",
        json={
            "material_properties": {
                "material_name": "Aluminium 6061",
                "density_kg_m3": 2700.0,
                "youngs_modulus_pa": 68.9e9,
            }
        },
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["fidelity_level"] == "behavioural"


async def test_delete_twin(
    app_client: AsyncClient, auth_headers: dict, test_project, test_twin
) -> None:
    r = await app_client.delete(
        f"/api/v1/projects/{test_project.id}/twins/{test_twin.id}",
        headers=auth_headers,
    )
    assert r.status_code == 204

    # Verify gone
    r2 = await app_client.get(
        f"/api/v1/projects/{test_project.id}/twins/{test_twin.id}",
        headers=auth_headers,
    )
    assert r2.status_code == 404


# ── OpenAPI spec ───────────────────────────────────────────────────────────

async def test_openapi_spec_accessible(app_client: AsyncClient) -> None:
    """OpenAPI spec must be reachable — CI tooling depends on it."""
    r = await app_client.get("/api/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"] == "EWC Compute Platform"
    # Verify all Phase 0 route groups are present
    paths = spec["paths"]
    assert "/health" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/projects" in paths



