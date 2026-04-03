"""
ATLAS Control System - Database Module
V3.2: PostgreSQL backend for high-volume production

Usage:
    from database import get_gallery_manager

    # Automatically selects JSON or PostgreSQL based on config
    manager = get_gallery_manager()
"""

import os
from pathlib import Path
from typing import Optional

# Check if PostgreSQL should be used
USE_POSTGRES = os.getenv("ATLAS_USE_POSTGRES", "0").lower() in ("1", "true", "yes")

# Import appropriate manager
if USE_POSTGRES:
    try:
        from .postgres_manager import (
            PostgresGalleryManager,
            SyncPostgresGalleryManager,
            DatabaseConfig,
            migrate_json_to_postgres,
        )
        POSTGRES_AVAILABLE = True
    except ImportError:
        POSTGRES_AVAILABLE = False
        USE_POSTGRES = False
else:
    POSTGRES_AVAILABLE = False


def get_gallery_manager(project_root: Optional[Path] = None, async_mode: bool = False):
    """
    Get the appropriate gallery manager based on configuration.

    Args:
        project_root: Root directory for JSON-based manager
        async_mode: If True and using PostgreSQL, return async manager

    Returns:
        RenderGalleryManager or PostgresGalleryManager instance
    """
    if USE_POSTGRES and POSTGRES_AVAILABLE:
        config = DatabaseConfig.from_env()
        if async_mode:
            return PostgresGalleryManager(config)
        else:
            return SyncPostgresGalleryManager(config)
    else:
        # Fall back to JSON-based manager
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from render_gallery_manager import RenderGalleryManager
        return RenderGalleryManager(project_root)


__all__ = [
    "get_gallery_manager",
    "USE_POSTGRES",
    "POSTGRES_AVAILABLE",
]

if POSTGRES_AVAILABLE:
    __all__.extend([
        "PostgresGalleryManager",
        "SyncPostgresGalleryManager",
        "DatabaseConfig",
        "migrate_json_to_postgres",
    ])
