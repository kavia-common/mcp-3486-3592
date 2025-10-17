from typing import Any, Dict, Optional

import httpx

from ..core.config import get_settings


class JiraService:
    """Lightweight JIRA REST client for essential operations."""

    def __init__(self, base_url: Optional[str] = None, email: Optional[str] = None, api_token: Optional[str] = None):
        s = get_settings()
        self.base_url = (base_url or s.JIRA_BASE_URL or "").rstrip("/")
        self.email = email or s.JIRA_EMAIL
        self.api_token = api_token or s.JIRA_API_TOKEN
        self._client = httpx.AsyncClient(base_url=self.base_url, auth=(self.email, self.api_token), timeout=20.0)

    async def close(self) -> None:
        await self._client.aclose()

    # PUBLIC_INTERFACE
    async def get_issue(self, issue_id_or_key: str) -> Dict[str, Any]:
        """Fetch a JIRA issue by id or key."""
        resp = await self._client.get(f"/rest/api/3/issue/{issue_id_or_key}")
        resp.raise_for_status()
        return resp.json()

    # PUBLIC_INTERFACE
    async def create_issue(self, project_key: str, summary: str, description: str, issue_type: str = "Task") -> Dict[str, Any]:
        """Create a JIRA issue."""
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
            }
        }
        resp = await self._client.post("/rest/api/3/issue", json=payload)
        resp.raise_for_status()
        return resp.json()

    # PUBLIC_INTERFACE
    async def add_comment(self, issue_id_or_key: str, body: str) -> Dict[str, Any]:
        """Add a comment to a JIRA issue."""
        payload = {"body": body}
        resp = await self._client.post(f"/rest/api/3/issue/{issue_id_or_key}/comment", json=payload)
        resp.raise_for_status()
        return resp.json()
