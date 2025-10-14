import logging
import sys
from typing import Optional

from .config import get_settings

# PUBLIC_INTERFACE
def configure_logging(level: Optional[int] = None) -> None:
    """Configure application-wide logging."""
    settings = get_settings()
    log_level = level if level is not None else (logging.DEBUG if settings.DEBUG else logging.INFO)

    # Basic configuration only once
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
    else:
        logging.getLogger().setLevel(log_level)
