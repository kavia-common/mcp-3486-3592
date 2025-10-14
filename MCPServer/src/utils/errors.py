from __future__ import annotations

import socket

import httpx
from sqlalchemy.exc import OperationalError, DBAPIError

from ..services.jira_client import JiraServerError, JiraRateLimitError


# PUBLIC_INTERFACE
def is_transient_error(exc: Exception) -> bool:
    """Heuristic to decide if an exception is transient and should be retried.

    Treat as transient:
    - Network/timeouts (httpx)
    - Socket errors
    - SQLAlchemy OperationalError or DBAPIError (non-integrity)
    - Jira server/rate-limit errors
    """
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, socket.timeout):
        return True
    if isinstance(exc, (OperationalError, DBAPIError)):
        return True
    if isinstance(exc, (JiraServerError, JiraRateLimitError)):
        return True
    return False
