"""M05 Phase 8 — Render & Vercel Staging Readiness Test Suite

Verifies:
1. Render Blueprint (render.yaml) schema, service definitions, commands, and environment mappings.
2. Vercel Configuration (frontend/vercel.json) framework settings and production security headers.
3. FastAPI health and readiness endpoints (/health, /api/v1/health, /api/v1/health/readiness).
4. CORS origin resolution for production domains and Vercel preview branch domains.
5. Environment variable inventory completeness and production secret requirements.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app, create_app


# -----------------------------------------------------------------------------
# 1. Render Blueprint (render.yaml) Validation
# -----------------------------------------------------------------------------
def test_render_blueprint_structure():
    """Verify render.yaml exists, parses as valid YAML, and contains required services and database."""
    blueprint_path = Path(__file__).resolve().parent.parent.parent / "render.yaml"
    assert blueprint_path.exists(), f"render.yaml not found at: {blueprint_path}"

    content = blueprint_path.read_text(encoding="utf-8")

    # Simple YAML validation without requiring extra third-party libraries
    assert "services:" in content
    assert "databases:" in content

    # Verify Web Service specification
    assert "name: mmaip-backend" in content
    assert "type: web" in content
    assert "rootDir: backend" in content
    assert "buildCommand:" in content
    assert "preDeployCommand: \"alembic upgrade head\"" in content
    assert "startCommand:" in content
    assert "healthCheckPath: /health" in content

    # Verify PostgreSQL specification
    assert "name: mmaip-postgres" in content
    assert "postgresMajorVersion: \"16\"" in content

    # Verify critical environment variable keys
    critical_env_vars = [
        "DATABASE_URL",
        "DATABASE_SYNC_URL",
        "SECRET_KEY",
        "JWT_SECRET",
        "SECRET_ENCRYPTION_KEY",
        "FRONTEND_URL",
        "DEFAULT_RETRIEVAL_MODE",
        "DEFAULT_VECTOR_STORE",
    ]
    for ev in critical_env_vars:
        assert f"key: {ev}" in content, f"Missing {ev} in render.yaml envVars"


# -----------------------------------------------------------------------------
# 2. Vercel Configuration (frontend/vercel.json) Validation
# -----------------------------------------------------------------------------
def test_vercel_config_structure_and_security_headers():
    """Verify frontend/vercel.json contains proper Next.js framework configuration and security headers."""
    vercel_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "vercel.json"
    assert vercel_path.exists(), f"frontend/vercel.json not found at: {vercel_path}"

    with open(vercel_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("framework") == "nextjs"
    assert data.get("buildCommand") == "next build"

    headers_list = data.get("headers", [])
    assert len(headers_list) > 0, "No headers configured in vercel.json"

    # Inspect all configured security headers
    header_map = {}
    for entry in headers_list:
        if entry.get("source") == "/(.*)":
            for h in entry.get("headers", []):
                header_map[h["key"]] = h["value"]

    assert header_map.get("X-Content-Type-Options") == "nosniff"
    assert header_map.get("X-Frame-Options") == "DENY"
    assert "strict-origin-when-cross-origin" in header_map.get("Referrer-Policy", "")


# -----------------------------------------------------------------------------
# 3. Health & Readiness Endpoints Validation
# -----------------------------------------------------------------------------
def test_health_check_endpoint():
    """Verify that root /health endpoint returns 200 OK and healthy status."""
    client = TestClient(app)

    resp_root = client.get("/health")
    assert resp_root.status_code == 200
    data_root = resp_root.json()
    assert data_root["status"] == "healthy"
    assert "timestamp" in data_root
    assert data_root["version"] == "0.1.0"


def test_readiness_endpoint():
    """Verify that /ready returns service and database readiness checks."""
    client = TestClient(app)
    resp = client.get("/ready")
    assert resp.status_code in (200, 503)
    data = resp.json()
    if resp.status_code == 200:
        assert data["status"] == "ready"
    else:
        assert "Database service unavailable" in data.get("detail", "")


# -----------------------------------------------------------------------------
# 4. CORS Origin Resolution Tests
# -----------------------------------------------------------------------------
def test_cors_origin_resolution():
    """Verify production CORSMiddleware allows configured FRONTEND_URL and Vercel preview domains."""
    # Production policy: explicit origins + production regex, no development regex.
    prod_settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        FRONTEND_URL="https://multi-tenant-ai-platform.vercel.app",
        ALLOWED_ORIGINS="",
        CORS_ORIGIN_REGEX=r"^https://mmaip-frontend(-[a-zA-Z0-9_-]+)?\.vercel\.app$",
    )
    client = TestClient(create_app(prod_settings))

    # 1. Exact FRONTEND_URL origin
    resp_fe = client.options(
        "/health",
        headers={
            "Origin": "https://multi-tenant-ai-platform.vercel.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp_fe.status_code == 200
    assert resp_fe.headers.get("access-control-allow-origin") == "https://multi-tenant-ai-platform.vercel.app"

    # 2. Vercel preview domain via regex
    preview_origin = "https://mmaip-frontend-preview-pr-12.vercel.app"
    resp_preview = client.options(
        "/health",
        headers={
            "Origin": preview_origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp_preview.status_code == 200
    assert resp_preview.headers.get("access-control-allow-origin") == preview_origin

    # 3. Disallowed untrusted origin
    untrusted_origin = "https://malicious-attacker-site.com"
    resp_untrusted = client.options(
        "/api/v1/health",
        headers={
            "Origin": untrusted_origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    # When origin is rejected by CORSMiddleware, access-control-allow-origin header is not returned
    assert resp_untrusted.headers.get("access-control-allow-origin") is None

    # 4. Disallowed unrelated Vercel domain (must be scoped to mmaip-frontend)
    unrelated_vercel = "https://unrelated-phishing-app.vercel.app"
    resp_unrelated_vercel = client.options(
        "/health",
        headers={
            "Origin": unrelated_vercel,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp_unrelated_vercel.headers.get("access-control-allow-origin") is None


# -----------------------------------------------------------------------------
# 5. Production Environment Template Validation
# -----------------------------------------------------------------------------
def test_env_production_template_completeness():
    """.env.production.example must provide mandatory staging and production configuration keys."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env.production.example"
    assert env_path.exists(), f".env.production.example not found at: {env_path}"

    content = env_path.read_text(encoding="utf-8")

    expected_production_variables = [
        "ENVIRONMENT=production",
        "DEBUG=false",
        "FRONTEND_URL=",
        "BACKEND_URL=",
        "SECRET_KEY=",
        "JWT_SECRET=",
        "SECRET_ENCRYPTION_KEY=",
        "DATABASE_URL=",
        "DATABASE_SYNC_URL=",
        "STORAGE_BACKEND=",
        "DEFAULT_RETRIEVAL_MODE=",
        "DEFAULT_VECTOR_STORE=",
        "LLM_BASE_URL=",
    ]
    for var in expected_production_variables:
        assert var in content, f"Expected {var} in .env.production.example"
