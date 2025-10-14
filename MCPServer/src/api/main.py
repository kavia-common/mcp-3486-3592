from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core.config import get_settings
from ..core.logging import configure_logging
from .routers.auth import router as auth_router
from .routers.users import router as users_router
from .routers.messages import router as messages_router
from .routers.rules import router as rules_router
from .routers.audit_logs import router as audit_logs_router

settings = get_settings()
configure_logging()

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(messages_router)
app.include_router(rules_router)
app.include_router(audit_logs_router)


@app.get("/", tags=["health"], summary="Health Check", description="Simple liveness check for the MCP Server.")
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}
