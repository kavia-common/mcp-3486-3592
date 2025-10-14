"""Background tasks package.

Provides startup/shutdown hooks for the background scheduler:
- startup_background_tasks
- shutdown_background_tasks
"""
from .background import startup_background_tasks, shutdown_background_tasks

__all__ = ["startup_background_tasks", "shutdown_background_tasks"]
