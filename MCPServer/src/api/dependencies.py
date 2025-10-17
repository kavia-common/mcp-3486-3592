from typing import AsyncGenerator

from .services.jira_service import JiraService


# PUBLIC_INTERFACE
async def get_jira_service() -> AsyncGenerator[JiraService, None]:
    """Provide an async JiraService instance and ensure proper cleanup."""
    svc = JiraService()
    try:
        yield svc
    finally:
        await svc.close()
