from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core.config import get_settings
from ..core.logging import configure_logging

settings = get_settings()
configure_logging()

app = FastAPI(
    title=settings.APP_NAME,
    description="MCP Server APIs for message processing and JIRA integration.",
    version="0.1.0",
    openapi_tags=[
        {"name": "health", "description": "Health and readiness checks"},
        {"name": "auth", "description": "Authentication endpoints"},
        {"name": "messages", "description": "Message processing APIs"},
        {"name": "jira", "description": "JIRA integration APIs"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["health"], summary="Health Check", description="Simple liveness check for the MCP Server.")
def health_check():
    return {"message": "Healthy"}
