from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from ..core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class JiraClientConfig:
    """Configuration holder for JiraClient."""
    base_url: str
    email_or_username: str
    api_token: str
    request_timeout: int = 30
    max_retries: int = 3
    backoff_base_seconds: float = 0.5
    backoff_max_seconds: float = 8.0


class JiraClientError(Exception):
    """Base exception for Jira client errors."""


class JiraAuthenticationError(JiraClientError):
    """Authentication or authorization failure with Jira."""


class JiraNotFoundError(JiraClientError):
    """Jira resource not found."""


class JiraRateLimitError(JiraClientError):
    """Jira rate limit exceeded."""


class JiraServerError(JiraClientError):
    """5xx error from Jira."""


def _build_config_from_env() -> JiraClientConfig:
    settings = get_settings()
    if not settings.JIRA_BASE_URL or not settings.JIRA_EMAIL or not settings.JIRA_API_TOKEN:
        raise JiraClientError(
            "JIRA configuration missing. Ensure JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN are set in environment."
        )
    return JiraClientConfig(
        base_url=settings.JIRA_BASE_URL.rstrip("/"),
        email_or_username=settings.JIRA_EMAIL,
        api_token=settings.JIRA_API_TOKEN,
        request_timeout=settings.REQUEST_TIMEOUT_SECONDS,
    )


# PUBLIC_INTERFACE
class JiraClient:
    """Async HTTP client for Jira REST API v3 with retry and backoff.

    Notes:
    - Uses Basic auth with email/token (for Atlassian Cloud).
    - Exposes key operations needed by MCP server.
    """

    def __init__(self, config: Optional[JiraClientConfig] = None, client: Optional[httpx.AsyncClient] = None) -> None:
        self._config = config or _build_config_from_env()
        # Basic auth for Atlassian cloud (email, api_token)
        auth = (self._config.email_or_username, self._config.api_token)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(self._config.request_timeout)
        self._client = client or httpx.AsyncClient(
            base_url=self._config.base_url,
            auth=auth,
            headers=headers,
            timeout=timeout,
        )

    async def _request_with_retries(
        self,
        method: str,
        url: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        expected_status: int | tuple[int, ...] = (200, 201, 204),
    ) -> httpx.Response:
        """Perform an HTTP request with exponential backoff on retryable errors."""
        max_retries = self._config.max_retries
        attempt = 0
        last_exc: Optional[Exception] = None

        while attempt <= max_retries:
            try:
                resp = await self._client.request(method, url, json=json, params=params)
                # Fast-path on expected statuses
                if isinstance(expected_status, int):
                    ok_statuses = (expected_status,)
                else:
                    ok_statuses = expected_status

                if resp.status_code in ok_statuses:
                    return resp

                # Handle categories
                if resp.status_code == 401 or resp.status_code == 403:
                    raise JiraAuthenticationError(f"Jira auth failed: {resp.status_code} {resp.text}")
                if resp.status_code == 404:
                    raise JiraNotFoundError(f"Jira resource not found: {url}")
                if resp.status_code == 429:
                    # Rate limited - attempt retry using Retry-After or backoff
                    retry_after = resp.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else self._compute_backoff(attempt)
                    logger.warning("Jira rate limited (429). Retrying in %.2fs (attempt %s/%s).", delay, attempt + 1, max_retries)
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                if 500 <= resp.status_code < 600:
                    # Server error - retry
                    delay = self._compute_backoff(attempt)
                    logger.warning(
                        "Jira server error %s. Retrying in %.2fs (attempt %s/%s). Body=%s",
                        resp.status_code, delay, attempt + 1, max_retries, resp.text[:500]
                    )
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue

                # Non-retryable unexpected
                raise JiraClientError(f"Unexpected Jira response {resp.status_code}: {resp.text[:500]}")

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_exc = e
                if attempt >= max_retries:
                    break
                delay = self._compute_backoff(attempt)
                logger.warning("Network/Timeout calling Jira: %s. Retrying in %.2fs (attempt %s/%s).", repr(e), delay, attempt + 1, max_retries)
                await asyncio.sleep(delay)
                attempt += 1
                continue

        if last_exc:
            raise JiraClientError(f"Failed to call Jira after {max_retries} retries") from last_exc
        raise JiraClientError(f"Failed to call Jira after {max_retries} retries (unknown error)")

    def _compute_backoff(self, attempt: int) -> float:
        delay = min(self._config.backoff_base_seconds * (2 ** attempt), self._config.backoff_max_seconds)
        # add small jitter
        return delay + min(0.25, delay * 0.1)

    async def aclose(self) -> None:
        """Close underlying HTTP client."""
        await self._client.aclose()

    # PUBLIC_INTERFACE
    async def create_issue(self, project_key: str, summary: str, description: Optional[str] = None, issue_type: str = "Task") -> Dict[str, Any]:
        """Create a Jira issue.

        Parameters:
        - project_key: Jira project key (e.g., 'ABC')
        - summary: Issue summary/title
        - description: Optional description
        - issue_type: Type name, default 'Task'

        Returns: Parsed JSON of created issue.
        """
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
            }
        }
        if description:
            payload["fields"]["description"] = description

        logger.debug("Creating Jira issue in project=%s summary=%s", project_key, summary)
        resp = await self._request_with_retries("POST", "/rest/api/3/issue", json=payload, expected_status=201)
        data = resp.json()
        logger.info("Created Jira issue key=%s id=%s", data.get("key"), data.get("id"))
        return data

    # PUBLIC_INTERFACE
    async def update_issue(self, issue_id_or_key: str, fields: Dict[str, Any]) -> None:
        """Update fields for a Jira issue.

        Parameters:
        - issue_id_or_key: ID or key (e.g., 'ABC-123')
        - fields: Fields under 'fields' object to update.
        """
        payload = {"fields": fields}
        logger.debug("Updating Jira issue=%s with fields=%s", issue_id_or_key, list(fields.keys()))
        await self._request_with_retries("PUT", f"/rest/api/3/issue/{issue_id_or_key}", json=payload, expected_status=204)
        logger.info("Updated Jira issue=%s", issue_id_or_key)

    # PUBLIC_INTERFACE
    async def add_comment(self, issue_id_or_key: str, comment_body: str) -> Dict[str, Any]:
        """Add a comment to a Jira issue.

        Parameters:
        - issue_id_or_key: Jira issue id or key
        - comment_body: The comment text
        """
        payload = {"body": comment_body}
        logger.debug("Adding comment to Jira issue=%s", issue_id_or_key)
        resp = await self._request_with_retries("POST", f"/rest/api/3/issue/{issue_id_or_key}/comment", json=payload, expected_status=201)
        data = resp.json()
        logger.info("Added comment id=%s to Jira issue=%s", data.get("id"), issue_id_or_key)
        return data

    # PUBLIC_INTERFACE
    async def get_issue(self, issue_id_or_key: str) -> Dict[str, Any]:
        """Retrieve a Jira issue by id or key."""
        logger.debug("Fetching Jira issue=%s", issue_id_or_key)
        resp = await self._request_with_retries("GET", f"/rest/api/3/issue/{issue_id_or_key}", expected_status=200)
        data = resp.json()
        logger.debug("Fetched Jira issue=%s fields_keys=%s", issue_id_or_key, list(data.keys()))
        return data
