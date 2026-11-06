from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.database.base import Base
from app.database.session import async_session_maker, check_db_connection, engine
from app.repositories.role_repository import RoleRepository
from app.schemas.health import HealthResponse, ReadinessResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: ensure tables exist if running on sqlite/local dev, and seed system roles
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with async_session_maker() as session:
            role_repo = RoleRepository(session)
            await role_repo.seed_system_roles_and_permissions()
            await session.commit()
    except Exception as e:
        # In Docker / production with migrations, alembic handles DDL
        print(f"[Startup Warning] Schema init or role seed: {e}")

    yield

    # Shutdown: dispose db pool
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Multi-Tenant AI Knowledge & Chatbot Platform API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
