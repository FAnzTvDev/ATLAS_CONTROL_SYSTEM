#!/usr/bin/env python3
"""
ATLAS V3.1 Configuration Module
================================
Centralizes all paths and settings via environment variables.
Enables portable deployment (local, cloud, Docker).

Usage:
    from config import Config

    output_dir = Config.ATLAS_OUTPUT_DIR
    tracking_db = Config.get_database_url()
"""

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


class Config:
    """Centralized configuration with environment variable support."""

    # ============================================================
    # BASE PATHS - Override via environment for portability
    # ============================================================

    # Root of the ATLAS control system
    ATLAS_ROOT = Path(os.getenv(
        "ATLAS_ROOT",
        Path(__file__).resolve().parent
    ))

    # Output directory for all generated assets
    ATLAS_OUTPUT_DIR = Path(os.getenv(
        "ATLAS_OUTPUT_DIR",
        Path.home() / "Desktop" / "atlas_output"
    ))

    # Cloud storage bucket — V18.0: Cloudflare R2 is sole cloud storage (GCS removed)
    CLOUD_STORAGE_BUCKET = os.getenv(
        "ATLAS_CLOUD_BUCKET",
        "r2://rumble-fanz"
    )

    # ============================================================
    # DERIVED PATHS (computed from base paths)
    # ============================================================

    @classmethod
    def get_project_output_dir(cls, project_slug: str) -> Path:
        """Get output directory for a specific project."""
        return cls.ATLAS_OUTPUT_DIR / project_slug

    @classmethod
    def get_pipeline_outputs_dir(cls) -> Path:
        """Get the pipeline outputs directory."""
        return cls.ATLAS_ROOT / "pipeline_outputs"

    @classmethod
    def get_manifest_dir(cls) -> Path:
        """Get the manifests directory."""
        return cls.ATLAS_ROOT / "manifests"

    @classmethod
    def get_template_dir(cls) -> Path:
        """Get the templates directory."""
        return cls.ATLAS_ROOT / "templates"

    @classmethod
    def get_character_dir(cls) -> Path:
        """Get the locked character library directory."""
        return cls.ATLAS_ROOT / "character_library_locked"

    @classmethod
    def get_fal_cache_dir(cls) -> Path:
        """Get the FAL asset cache directory."""
        return cls.ATLAS_ROOT / "fal_cache"

    # ============================================================
    # PROJECT-SPECIFIC OUTPUT DIRECTORIES
    # ============================================================

    @classmethod
    def get_nano_banana_dir(cls) -> Path:
        """Get the Nano Banana output directory."""
        return cls.ATLAS_OUTPUT_DIR / "nano_banana"

    @classmethod
    def get_blackwood_dir(cls) -> Path:
        """Get the Blackwood Estate output directory."""
        return cls.ATLAS_OUTPUT_DIR / "blackwood_estate"

    @classmethod
    def get_ravencroft_dir(cls, version: str = "V3_FIXED") -> Path:
        """Get Ravencroft output directory for a specific version."""
        return cls.ATLAS_OUTPUT_DIR / f"RAVENCROFT_{version}"

    @classmethod
    def get_versioned_output_dir(cls, version: str) -> Path:
        """Get versioned output directory (V5, V6, V7, etc.)."""
        version_map = {
            "v5": "RAVENCROFT_V5_CINEMATIC",
            "v6": "RAVENCROFT_V6_METALOOP",
            "v7": "RAVENCROFT_V7_QUANTUM",
            "v8": "RAVENCROFT_V8_COMPLETE",
            "v9": "RAVENCROFT_V9_15_SCENES",
            "v10": "RAVENCROFT_V10_COMPLETION",
        }
        dirname = version_map.get(version.lower(), f"RAVENCROFT_{version.upper()}")
        return cls.ATLAS_OUTPUT_DIR / dirname

    # ============================================================
    # DATABASE CONFIGURATION
    # ============================================================

    # Database URL - supports SQLite (default), PostgreSQL, MySQL
    DATABASE_URL = os.getenv(
        "ATLAS_DATABASE_URL",
        None  # None means use JSON file fallback
    )

    # PostgreSQL-specific settings (V3.2)
    POSTGRES_HOST = os.getenv("ATLAS_DB_HOST", "localhost")
    POSTGRES_PORT = int(os.getenv("ATLAS_DB_PORT", "5432"))
    POSTGRES_DB = os.getenv("ATLAS_DB_NAME", "atlas_control")
    POSTGRES_USER = os.getenv("ATLAS_DB_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("ATLAS_DB_PASSWORD", "")

    # Use PostgreSQL instead of JSON (V3.2)
    USE_POSTGRES = os.getenv("ATLAS_USE_POSTGRES", "0").lower() in ("1", "true", "yes")

    # JSON tracking file (fallback when no DB configured)
    TRACKING_JSON_PATH = Path(os.getenv(
        "ATLAS_TRACKING_JSON",
        str(ATLAS_ROOT / "render_tracking.json")
    ))

    @classmethod
    def get_database_url(cls) -> Optional[str]:
        """Get database URL if configured, None for JSON fallback."""
        if cls.DATABASE_URL:
            return cls.DATABASE_URL
        if cls.USE_POSTGRES:
            # Build PostgreSQL URL from individual settings
            pwd_part = f":{cls.POSTGRES_PASSWORD}" if cls.POSTGRES_PASSWORD else ""
            return f"postgresql://{cls.POSTGRES_USER}{pwd_part}@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}"
        return None

    @classmethod
    def use_database(cls) -> bool:
        """Check if a proper database is configured (not JSON)."""
        return cls.DATABASE_URL is not None or cls.USE_POSTGRES

    @classmethod
    def get_database_type(cls) -> str:
        """Get database type: postgresql, mysql, sqlite, or json."""
        if cls.USE_POSTGRES:
            return "postgresql"
        if not cls.DATABASE_URL:
            return "json"
        parsed = urlparse(cls.DATABASE_URL)
        return parsed.scheme.replace("+asyncpg", "").replace("+psycopg2", "")

    # ============================================================
    # API KEYS - ALWAYS use environment variables
    # ============================================================

    FAL_KEY = os.getenv("FAL_KEY", "")
    REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
    ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

    # Multiple Replicate tokens for parallel processing
    @classmethod
    def get_replicate_tokens(cls) -> list:
        """Get list of Replicate API tokens for rotation."""
        tokens_str = os.getenv("REPLICATE_TOKENS", "")
        if tokens_str:
            return [t.strip() for t in tokens_str.split(",") if t.strip()]
        elif cls.REPLICATE_API_TOKEN:
            return [cls.REPLICATE_API_TOKEN]
        return []

    # ============================================================
    # SERVER CONFIGURATION
    # ============================================================

    HOST = os.getenv("ATLAS_HOST", "0.0.0.0")
    PORT = int(os.getenv("ATLAS_PORT", "9999"))
    DEBUG = os.getenv("ATLAS_DEBUG", "false").lower() == "true"

    # Multi-tenancy
    ENABLE_AUTH = os.getenv("ATLAS_ENABLE_AUTH", "false").lower() == "true"
    AUTH_SECRET_KEY = os.getenv("ATLAS_AUTH_SECRET", "dev-secret-change-in-production")

    # ============================================================
    # CLOUD STORAGE ABSTRACTION
    # ============================================================

    @classmethod
    def get_storage_backend(cls) -> str:
        """Determine storage backend: 'local', 'r2', or 's3'. GCS removed in V18.0."""
        bucket = cls.CLOUD_STORAGE_BUCKET
        if bucket.startswith("r2://"):
            return "r2"
        elif bucket.startswith("gs://"):
            return "r2"  # V18.0: GCS removed, treat as R2
        elif bucket.startswith("s3://"):
            return "s3"
        else:
            return "local"

    @classmethod
    def get_public_url(cls, relative_path: str) -> str:
        """
        Convert a relative path to a public URL.

        Local: file:///path/to/file
        R2: {ATLAS_R2_PUBLIC_URL}/atlas-frames/{path}
        S3: https://bucket.s3.region.amazonaws.com/path
        """
        backend = cls.get_storage_backend()

        if backend == "local":
            full_path = cls.ATLAS_OUTPUT_DIR / relative_path
            return f"file://{full_path}"

        elif backend == "r2":
            r2_public = os.getenv("ATLAS_R2_PUBLIC_URL", "")
            if r2_public:
                return f"{r2_public.rstrip('/')}/atlas-frames/{relative_path}"
            return relative_path

        elif backend == "s3":
            bucket_name = cls.CLOUD_STORAGE_BUCKET.replace("s3://", "")
            region = os.getenv("AWS_REGION", "us-east-1")
            return f"https://{bucket_name}.s3.{region}.amazonaws.com/{relative_path}"

        return relative_path

    # ============================================================
    # MEDIA ROOTS (for StaticFiles mounts)
    # ============================================================

    @classmethod
    def get_media_roots(cls) -> list:
        """Get list of directories to serve as static files."""
        return [
            cls.get_nano_banana_dir(),
            cls.get_blackwood_dir(),
            cls.ATLAS_OUTPUT_DIR,
            cls.get_pipeline_outputs_dir(),
            cls.get_character_dir(),  # For AI actor images
            cls.ATLAS_ROOT,  # For any file under ATLAS_CONTROL_SYSTEM
        ]

    # ============================================================
    # LOGGING
    # ============================================================

    LOG_LEVEL = os.getenv("ATLAS_LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("ATLAS_LOG_FILE", "")  # Empty = stdout only

    @classmethod
    def get_quantum_log_path(cls) -> Path:
        """Get path for quantum enhancement log."""
        return cls.ATLAS_OUTPUT_DIR / "quantum_enhancement_log.json"

    # ============================================================
    # INITIALIZATION
    # ============================================================

    @classmethod
    def ensure_directories(cls):
        """Create all required directories if they don't exist."""
        dirs = [
            cls.ATLAS_OUTPUT_DIR,
            cls.get_nano_banana_dir(),
            cls.get_blackwood_dir(),
            cls.get_pipeline_outputs_dir(),
            cls.get_manifest_dir(),
            cls.get_template_dir(),
            cls.get_character_dir(),
            cls.get_fal_cache_dir(),
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def print_config(cls):
        """Print current configuration for debugging."""
        print("=" * 60)
        print("ATLAS V3.1 CONFIGURATION")
        print("=" * 60)
        print(f"ATLAS_ROOT:       {cls.ATLAS_ROOT}")
        print(f"ATLAS_OUTPUT_DIR: {cls.ATLAS_OUTPUT_DIR}")
        print(f"CLOUD_BUCKET:     {cls.CLOUD_STORAGE_BUCKET}")
        print(f"STORAGE_BACKEND:  {cls.get_storage_backend()}")
        print(f"DATABASE_TYPE:    {cls.get_database_type()}")
        print(f"HOST:             {cls.HOST}:{cls.PORT}")
        print(f"AUTH_ENABLED:     {cls.ENABLE_AUTH}")
        print(f"DEBUG:            {cls.DEBUG}")
        print("=" * 60)


# Ensure directories exist on import
Config.ensure_directories()
