from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import Settings, settings
from app.core.cors import build_cors_policy
from app.database.session import async_session_maker, check_db_connection, engine
from app.models import Base
from app.repositories.role_repository import RoleRepository
from app.schemas.health import HealthResponse, ReadinessResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Fail-closed production storage validation (never silently use ephemeral local storage)
    from app.storage import validate_storage_configuration

    validate_storage_configuration(settings)

    # Startup: ensure tables exist if running on sqlite/local dev, and seed system roles
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with async_session_maker() as session:
            role_repo = RoleRepository(session)
            await role_repo.seed_system_roles_and_permissions()
            await session.commit()

        # Recover any orphaned background ingestion / embedding jobs from previous crashes
        async with async_session_maker() as session:
            from app.services.ingestion.recovery import recover_orphaned_jobs

            stats = await recover_orphaned_jobs(session)
            if stats["recovered_ingestion_jobs"] > 0 or stats["recovered_embedding_jobs"] > 0:
                print(f"[Lifespan] Recovered orphaned background jobs: {stats}")
    except Exception as e:
        # In Docker / production with migrations, alembic handles DDL
        print(f"[Startup Warning] Schema init, role seed, or job recovery: {e}")

    yield

    # Shutdown: dispose db pool
    await engine.dispose()


def create_app(app_settings: Settings = settings) -> FastAPI:
    """Application factory with centralized, environment-aware CORS policy."""
    app = FastAPI(
        title=app_settings.PROJECT_NAME,
        description="Enterprise Multi-Tenant AI Knowledge & Chatbot Platform API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS configuration (centralized policy: explicit production origins,
    # development-only private-network regex, fail-closed on invalid prod config)
    origins, origin_regex = build_cors_policy(app_settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse, tags=["System Health"])
    async def health_check() -> HealthResponse:
        """Verifies that the application process is running and alive."""
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(UTC),
            version="0.1.0",
        )

    @app.get("/ready", response_model=ReadinessResponse, tags=["System Health"])
    async def readiness_check() -> ReadinessResponse:
        """Verifies database connectivity and readiness to serve traffic."""
        is_ready = await check_db_connection()
        if not is_ready:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable",
            )
        return ReadinessResponse(
            status="ready",
            database="connected",
            timestamp=datetime.now(UTC),
        )

    # Mount versioned API
    app.include_router(api_v1_router)
    return app


app = create_app()
