import logging
import sys


# PUBLIC_INTERFACE
def configure_logging(level: int | str = logging.INFO) -> None:
    """Configure root logger with a simple formatter directed to stdout."""
    root = logging.getLogger()
    root.setLevel(level)
    # Clear existing handlers to avoid duplication during reloads
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
