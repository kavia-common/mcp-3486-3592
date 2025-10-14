from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..core.config import get_settings
from ..core.logging import configure_logging
from ..db.session import engine
from ..db.models import Base  # ensures models metadata is available for create_all
from ..tasks import startup_background_tasks, shutdown_background_tasks
from ..db.seed import run_seed_if_enabled
from ..utils import errors as error_utils

# Routers
from .routers.auth import router as auth_router
from .routers.users import router as users_router
from .routers.messages import router as messages_router
from .routers.rules import router as rules_router
from .routers.audit_logs import router as audit_logs_router
from .routers.jira_sync import router as jira_sync_router

# Initialize settings and logging early
settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app with metadata and tags
app = FastAPI(
    title=settings.APP_NAME,
    description="MCP Server APIs for message processing and JIRA integration.",
    version="0.1.0",
    openapi_tags=[
        {"name": "health", "description": "Health and readiness checks"},
        {"name": "auth", "description": "Authentication endpoints"},
        {"name": "users", "description": "User management (admin-only)"},
        {"name": "messages", "description": "Message processing APIs"},
        {"name": "rules", "description": "Rule management APIs"},
        {"name": "jira", "description": "JIRA integration APIs"},
        {"name": "audit-logs", "description": "Audit Logs query APIs (admin only)"},
    ],
)

# CORS configured from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register global exception handlers leveraging utils/errors.py
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handle uncaught exceptions globally.

    If the error is considered transient (per utils.errors.is_transient_error),
    return a 503 Service Unavailable to hint clients they may retry.
    Otherwise, return a 500 Internal Server Error with minimal details.
    """
    status_code = 503 if error_utils.is_transient_error(exc) else 500
    # Log with traceback
    logger.exception("Unhandled error on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": "Service temporarily unavailable" if status_code == 503 else "Internal server error"
        },
    )

# Include all routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(messages_router)
app.include_router(rules_router)
app.include_router(audit_logs_router)
app.include_router(jira_sync_router)


@app.on_event("startup")
async def _startup() -> None:
    """
    Application startup hook.

    - In development environment, initialize database tables via Base.metadata.create_all(engine).
    - Start background scheduler for message and JIRA sync processing.
    """
    try:
        if settings.ENV.lower() == "development":
            logger.info("Development environment detected; creating database tables if missing...")
            Base.metadata.create_all(bind=engine)
            # Run optional seed in development if enabled via env flag
            try:
                run_seed_if_enabled()
            except Exception as se:  # pragma: no cover - defensive
                logger.exception("Seeding failed: %s", se)
    except Exception as e:  # pragma: no cover - defensive: log but do not block startup in prod
        logger.exception("Failed to initialize database schema: %s", e)
        # In dev we still proceed to start to allow troubleshooting
    await startup_background_tasks()
    logger.info("Startup completed.")


@app.on_event("shutdown")
async def _shutdown() -> None:
    """
    Application shutdown hook.

    - Stop background scheduler gracefully.
    """
    await shutdown_background_tasks()
    logger.info("Shutdown completed.")


# PUBLIC_INTERFACE
@app.get(
    "/",
    tags=["health"],
    summary="Health Check",
    description="Simple liveness check for the MCP Server."
)
def health_check() -> dict:
    """Health check endpoint returning basic liveness info."""
    return {"message": "Healthy"}
