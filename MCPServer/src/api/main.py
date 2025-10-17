from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from .core.config import get_settings
from .core.logging import configure_logging
from .models.db import Base, engine
from .routers.auth import router as auth_router
from .routers.users import router as users_router
from .routers.messages import router as messages_router
from .routers.rules import router as rules_router
from .routers.audit import router as audit_router
from .routers.jira import router as jira_router
from .events.webhooks import router as webhooks_router

settings = get_settings()
configure_logging()

openapi_tags = [
    {"name": "auth", "description": "Authentication and authorization"},
    {"name": "users", "description": "User management"},
    {"name": "messages", "description": "Message lifecycle operations"},
    {"name": "rules", "description": "Rule management"},
    {"name": "audit", "description": "Audit logs"},
    {"name": "jira", "description": "JIRA integration endpoints"},
    {"name": "webhooks", "description": "Incoming webhook receivers"},
    {"name": "health", "description": "Health check"},
]

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ALLOW_ORIGINS.split(",")] if settings.CORS_ALLOW_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    # Auto-create tables for MVP
    async with engine.begin() as conn:  # type: ignore[var-annotated]
        await conn.run_sync(Base.metadata.create_all)


@app.get(
    "/health",
    tags=["health"],
    summary="Health Check",
    description="Return service health information.",
)
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


# Routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(messages_router)
app.include_router(rules_router)
app.include_router(audit_router)
app.include_router(jira_router)
app.include_router(webhooks_router)
