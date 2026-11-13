import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import Settings, api_docs_enabled, settings, should_initialize_schema
from app.core.cors import build_cors_policy
from app.database.session import async_session_maker, check_db_connection, engine
from app.models import Base
from app.repositories.role_repository import RoleRepository
from app.schemas.health import HealthResponse, ReadinessResponse

logger = logging.getLogger("mmaip.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Fail-closed production storage validation (never silently use ephemeral local storage)
    from app.storage import validate_storage_configuration

    validate_storage_configuration(settings)

    dispatcher_stop: asyncio.Event | None = None
    dispatcher_task: asyncio.Task[None] | None = None

    # Startup: ensure tables exist if running on sqlite/local dev, and seed system roles
    try:
        if should_initialize_schema(settings):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        async with async_session_maker() as session:
            role_repo = RoleRepository(session)
            await role_repo.seed_system_roles_and_permissions()
            await session.commit()

        # Recover interrupted background jobs. Ingestion recovery is lease
        # aware (requeue while retries remain, terminal on exhaustion); fresh
        # PROCESSING jobs owned by a live sibling process are left untouched.
        async with async_session_maker() as session:
            from app.services.ingestion.recovery import recover_orphaned_jobs

            stats = await recover_orphaned_jobs(session)
            if stats["recovered_ingestion_jobs"] > 0 or stats["recovered_embedding_jobs"] > 0:
                print(f"[Lifespan] Recovered orphaned background jobs: {stats}")

        # Idempotent second sweep for rows that became stale after the first
        # pass (or when recovery.py is bypassed by another entry point).
        async with async_session_maker() as session:
            from app.services.ingestion.job_queue import recover_stale_jobs

            stale_stats = await recover_stale_jobs(session, settings.INGESTION_LEASE_SECONDS)
            if stale_stats["recovered"] > 0:
                print(f"[Lifespan] Lease recovery: {stale_stats}")

    except Exception as e:
        # In Docker / production with migrations, alembic handles DDL
        print(f"[Startup Warning] Schema init, role seed, or job recovery: {e}")

    # Start the dispatcher even if a recovery sweep failed: QUEUED jobs must
    # still be picked up. API upload tasks and a standalone worker also claim
    # atomically, so duplicate dispatch cannot double-process a job.
    if settings.INGESTION_INLINE_DISPATCHER_ENABLED:
        try:
            from app.services.ingestion.job_queue import dispatch_pending_jobs

            dispatcher_stop = asyncio.Event()
            dispatcher_task = asyncio.create_task(
                dispatch_pending_jobs(
                    async_session_maker,
                    dispatcher_stop,
                    settings.INGESTION_DISPATCHER_POLL_SECONDS,
                    settings.INGESTION_MAX_CONCURRENCY,
                ),
                name="ingestion-inline-dispatcher",
            )
            print(
                "[Lifespan] Inline ingestion dispatcher started "
                f"(poll={settings.INGESTION_DISPATCHER_POLL_SECONDS}s, "
                f"concurrency={settings.INGESTION_MAX_CONCURRENCY}, "
                f"lease={settings.INGESTION_LEASE_SECONDS}s)"
            )
        except Exception as e:
            print(f"[Startup Warning] Inline ingestion dispatcher failed to start: {e}")

    yield

    # Shutdown: stop claiming new jobs, let the in-flight job drain briefly,
    # then cancel if it exceeds the shutdown budget (lease recovery will
    # requeue it on the next startup).
    if dispatcher_stop is not None:
        dispatcher_stop.set()
    if dispatcher_task is not None:
        try:
            await asyncio.wait_for(dispatcher_task, timeout=30)
        except TimeoutError:
            print("[Shutdown] Inline ingestion dispatcher did not drain in 30s; cancelling.")
            dispatcher_task.cancel()
            try:
                await dispatcher_task
            except asyncio.CancelledError:
                pass
        except Exception as e:
            print(f"[Shutdown Warning] Inline ingestion dispatcher exited with error: {e}")

    # Shutdown: dispose db pool
    await engine.dispose()


def create_app(app_settings: Settings = settings) -> FastAPI:
    """Application factory with centralized, environment-aware CORS policy."""
    # API docs are development-only by default; ENABLE_API_DOCS overrides the
    # environment-derived default. When disabled the routes are never mounted.
    docs_enabled = api_docs_enabled(app_settings)
    app = FastAPI(
        title=app_settings.PROJECT_NAME,
        description="Enterprise Multi-Tenant AI Knowledge & Chatbot Platform API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
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
        """Liveness probe: confirms the process is running without touching the DB."""
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(UTC),
            version="0.1.0",
        )

    @app.get("/ready", response_model=ReadinessResponse, tags=["System Health"])
    async def readiness_check() -> ReadinessResponse:
        """Readiness probe: verifies database connectivity.

        This endpoint is public (no authentication). Each call performs a real
        database round-trip, so external monitors hitting it wake an idle Neon
        compute. Do not add in-app periodic polling against this route; rely on
        the hosting platform health check instead.
        """
        try:
            is_ready = await check_db_connection()
        except Exception as exc:
            # Never surface driver errors, DSNs, or stack details to the caller.
            logger.warning("Readiness database probe failed: %s", type(exc).__name__)
            is_ready = False
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
