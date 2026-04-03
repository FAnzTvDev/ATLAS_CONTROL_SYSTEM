#!/usr/bin/env python3
"""
ATLAS Control System - PostgreSQL Database Manager
V3.2: High-performance database backend for 9000+ shot production

Provides:
- Async PostgreSQL connection pooling
- CRUD operations for shots, scenes, stats
- Migration from JSON to PostgreSQL
- Backwards-compatible API with RenderGalleryManager
"""

import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """PostgreSQL connection configuration"""
    host: str = "localhost"
    port: int = 5432
    database: str = "atlas_control"
    user: str = os.environ.get("USER", "postgres")  # Use current username as default
    password: str = ""
    min_connections: int = 2
    max_connections: int = 10

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Load config from environment variables"""
        # Default user to current system user (works on Mac without password)
        default_user = os.environ.get("USER", "postgres")
        return cls(
            host=os.getenv("ATLAS_DB_HOST", "localhost"),
            port=int(os.getenv("ATLAS_DB_PORT", "5432")),
            database=os.getenv("ATLAS_DB_NAME", "atlas_control"),
            user=os.getenv("ATLAS_DB_USER", default_user),
            password=os.getenv("ATLAS_DB_PASSWORD", ""),
            min_connections=int(os.getenv("ATLAS_DB_MIN_CONN", "2")),
            max_connections=int(os.getenv("ATLAS_DB_MAX_CONN", "10")),
        )


class PostgresGalleryManager:
    """
    PostgreSQL-backed render gallery manager.
    Drop-in replacement for RenderGalleryManager with same API.
    """

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig.from_env()
        self._pool: Optional[asyncpg.Pool] = None
        self._sync_conn = None  # For synchronous operations

        # Cache for stats (reduces DB queries)
        self._stats_cache: Dict[str, int] = {}
        self._stats_cache_time: Optional[datetime] = None
        self._stats_cache_ttl = 5  # seconds

    async def connect(self) -> bool:
        """Initialize async connection pool"""
        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg not installed")
            return False

        try:
            self._pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                min_size=self.config.min_connections,
                max_size=self.config.max_connections,
            )
            logger.info(f"Connected to PostgreSQL: {self.config.database}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            return False

    def connect_sync(self) -> bool:
        """Initialize synchronous connection"""
        if not PSYCOPG2_AVAILABLE:
            logger.error("psycopg2 not installed")
            return False

        try:
            self._sync_conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                dbname=self.config.database,
                user=self.config.user,
                password=self.config.password,
            )
            self._sync_conn.autocommit = True
            logger.info(f"Connected to PostgreSQL (sync): {self.config.database}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            return False

    async def close(self):
        """Close connection pool"""
        if self._pool:
            await self._pool.close()
        if self._sync_conn:
            self._sync_conn.close()

    # =========================================================================
    # SHOT OPERATIONS
    # =========================================================================

    async def register_shot(
        self,
        shot_id: str,
        scene_id: str,
        video_path: Optional[str] = None,
        image_path: Optional[str] = None,
        status: str = "new",
        metadata: Optional[Dict] = None
    ) -> bool:
        """Register a new shot or update existing"""
        if not self._pool:
            return False

        metadata = metadata or {}

        try:
            async with self._pool.acquire() as conn:
                # Upsert shot
                await conn.execute("""
                    INSERT INTO shots (
                        shot_id, scene_id, project, episode, status,
                        video_path, image_path, nano_prompt, ltx_motion_prompt,
                        shot_size, duration, coverage_type, characters,
                        location, lighting, camera, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                    ON CONFLICT (shot_id) DO UPDATE SET
                        scene_id = EXCLUDED.scene_id,
                        project = COALESCE(EXCLUDED.project, shots.project),
                        episode = COALESCE(EXCLUDED.episode, shots.episode),
                        status = EXCLUDED.status,
                        video_path = COALESCE(EXCLUDED.video_path, shots.video_path),
                        image_path = COALESCE(EXCLUDED.image_path, shots.image_path),
                        nano_prompt = COALESCE(EXCLUDED.nano_prompt, shots.nano_prompt),
                        metadata = shots.metadata || EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    shot_id,
                    scene_id,
                    metadata.get("project"),
                    metadata.get("episode"),
                    status,
                    video_path,
                    image_path,
                    metadata.get("nano_prompt"),
                    metadata.get("ltx_motion_prompt"),
                    metadata.get("shot_size"),
                    metadata.get("duration"),
                    metadata.get("coverage_type"),
                    metadata.get("characters", []),
                    metadata.get("location"),
                    metadata.get("lighting"),
                    metadata.get("camera"),
                    json.dumps(metadata),
                )

                # Ensure scene exists
                await conn.execute("""
                    INSERT INTO scenes (scene_id, project, episode)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (scene_id) DO UPDATE SET
                        project = COALESCE(EXCLUDED.project, scenes.project),
                        episode = COALESCE(EXCLUDED.episode, scenes.episode),
                        shot_count = (SELECT COUNT(*) FROM shots WHERE scene_id = $1),
                        updated_at = CURRENT_TIMESTAMP
                """, scene_id, metadata.get("project"), metadata.get("episode"))

                # Update stats
                await self._increment_stat(conn, "total_generated")
                if status == "working":
                    await self._increment_stat(conn, "working")

            logger.info(f"Registered shot: {shot_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to register shot {shot_id}: {e}")
            return False

    async def get_shot(self, shot_id: str) -> Optional[Dict]:
        """Get shot by ID"""
        if not self._pool:
            return None

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM shots WHERE shot_id = $1", shot_id
                )
                if row:
                    return dict(row)
        except Exception as e:
            logger.error(f"Failed to get shot {shot_id}: {e}")
        return None

    async def mark_shot(self, shot_id: str, status: str) -> bool:
        """Update shot status"""
        if not self._pool:
            return False

        try:
            async with self._pool.acquire() as conn:
                # Get old status for stats adjustment
                old_status = await conn.fetchval(
                    "SELECT status FROM shots WHERE shot_id = $1", shot_id
                )

                if not old_status:
                    logger.warning(f"Shot {shot_id} not found")
                    return False

                if old_status == status:
                    return True  # No change needed

                # Update status
                await conn.execute(
                    "UPDATE shots SET status = $1 WHERE shot_id = $2",
                    status, shot_id
                )

                # Adjust stats
                await self._decrement_stat(conn, old_status)
                await self._increment_stat(conn, status)

            logger.info(f"Marked shot {shot_id} as {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to mark shot {shot_id}: {e}")
            return False

    async def get_scene_shots(self, scene_id: str) -> List[str]:
        """Get all shot IDs for a scene"""
        if not self._pool:
            return []

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT shot_id FROM shots WHERE scene_id = $1 ORDER BY shot_id",
                    scene_id
                )
                return [row["shot_id"] for row in rows]
        except Exception as e:
            logger.error(f"Failed to get scene shots: {e}")
            return []

    async def get_shots_by_project(
        self,
        project: str,
        scene_id: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """Get shots filtered by project and optionally scene"""
        if not self._pool:
            return []

        try:
            async with self._pool.acquire() as conn:
                if scene_id:
                    rows = await conn.fetch("""
                        SELECT * FROM shots
                        WHERE project = $1 AND scene_id = $2
                        ORDER BY shot_id
                        LIMIT $3
                    """, project, scene_id, limit)
                else:
                    rows = await conn.fetch("""
                        SELECT * FROM shots
                        WHERE project = $1
                        ORDER BY shot_id
                        LIMIT $2
                    """, project, limit)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get project shots: {e}")
            return []

    async def get_all_shots(self, limit: int = 10000) -> List[Dict]:
        """
        Get ALL shots from database (across all projects).
        V15.3: Added for backwards compatibility with RenderGalleryManager.

        Args:
            limit: Maximum number of shots to return (default 10000)

        Returns:
            List of shot dictionaries
        """
        if not self._pool:
            return []

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM shots
                    ORDER BY project, scene_id, shot_id
                    LIMIT $1
                """, limit)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get all shots: {e}")
            return []

    # =========================================================================
    # SCENE OPERATIONS
    # =========================================================================

    async def is_scene_complete(self, scene_id: str) -> bool:
        """Check if all shots in scene are marked as 'working'"""
        if not self._pool:
            return False

        try:
            async with self._pool.acquire() as conn:
                # Count total shots vs working shots
                result = await conn.fetchrow("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'working' THEN 1 ELSE 0 END) as working
                    FROM shots WHERE scene_id = $1
                """, scene_id)

                if result and result["total"] > 0:
                    return result["total"] == result["working"]
        except Exception as e:
            logger.error(f"Failed to check scene completion: {e}")
        return False

    async def update_scene_stitch(self, scene_id: str, stitched_path: str) -> bool:
        """Update scene with stitched video path"""
        if not self._pool:
            return False

        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    UPDATE scenes SET
                        stitched_path = $1,
                        status = 'complete'
                    WHERE scene_id = $2
                """, stitched_path, scene_id)

                await self._increment_stat(conn, "scenes_stitched")
            return True
        except Exception as e:
            logger.error(f"Failed to update scene stitch: {e}")
            return False

    # =========================================================================
    # STATS OPERATIONS
    # =========================================================================

    async def _increment_stat(self, conn, stat_key: str):
        """Increment a stat counter"""
        # Map status to stat key
        stat_map = {
            "new": "total_generated",
            "working": "working",
            "needs_regen": "needs_regen",
            "ready_for_video": "ready_for_video",
            "image_pending_video": "image_pending",
        }
        key = stat_map.get(stat_key, stat_key)

        await conn.execute("""
            INSERT INTO render_stats (stat_key, stat_value) VALUES ($1, 1)
            ON CONFLICT (stat_key) DO UPDATE SET
                stat_value = render_stats.stat_value + 1,
                updated_at = CURRENT_TIMESTAMP
        """, key)

    async def _decrement_stat(self, conn, stat_key: str):
        """Decrement a stat counter"""
        stat_map = {
            "new": "total_generated",
            "working": "working",
            "needs_regen": "needs_regen",
            "ready_for_video": "ready_for_video",
            "image_pending_video": "image_pending",
        }
        key = stat_map.get(stat_key, stat_key)

        await conn.execute("""
            UPDATE render_stats SET
                stat_value = GREATEST(0, stat_value - 1),
                updated_at = CURRENT_TIMESTAMP
            WHERE stat_key = $1
        """, key)

    async def get_stats(self) -> Dict[str, int]:
        """Get all stats"""
        if not self._pool:
            return {}

        # Check cache
        now = datetime.now(tz=timezone.utc)
        if self._stats_cache_time and (now - self._stats_cache_time).seconds < self._stats_cache_ttl:
            return self._stats_cache

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("SELECT stat_key, stat_value FROM render_stats")
                self._stats_cache = {row["stat_key"]: row["stat_value"] for row in rows}
                self._stats_cache_time = now
                return self._stats_cache
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

    # =========================================================================
    # PROJECT OPERATIONS
    # =========================================================================

    async def list_projects(self) -> Dict[str, Dict[str, Any]]:
        """List all projects with their scenes and episodes"""
        if not self._pool:
            return {}

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT
                        COALESCE(project, 'Unassigned') as project,
                        array_agg(DISTINCT scene_id) as scenes,
                        array_agg(DISTINCT episode) FILTER (WHERE episode IS NOT NULL) as episodes,
                        COUNT(*) as shot_count
                    FROM shots
                    GROUP BY project
                    ORDER BY project
                """)

                return {
                    row["project"]: {
                        "scenes": list(set(row["scenes"] or [])),
                        "episodes": list(set(row["episodes"] or [])),
                        "shot_count": row["shot_count"]
                    }
                    for row in rows
                }
        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
            return {}

    # =========================================================================
    # IMAGE METADATA OPERATIONS
    # =========================================================================

    async def load_image_metadata(self, shot_id: str) -> Optional[Dict]:
        """Load image metadata for a shot"""
        if not self._pool:
            return None

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM image_metadata WHERE shot_id = $1", shot_id
                )
                if row:
                    return dict(row)
        except Exception as e:
            logger.error(f"Failed to load image metadata: {e}")
        return None

    async def update_image_metadata(self, shot_id: str, updates: Dict) -> Optional[Dict]:
        """Update image metadata for a shot"""
        if not self._pool:
            return None

        try:
            async with self._pool.acquire() as conn:
                # Build dynamic update
                allowed_fields = {
                    "review_prompt", "video_prompt_override", "director_notes",
                    "dinov2_guideline", "dinov2_notes", "dialogue_text",
                    "continuity_prompt", "lock_final", "image_generations",
                    "video_generations", "image_cost_total_usd", "video_cost_total_usd"
                }

                fields = {k: v for k, v in updates.items() if k in allowed_fields}
                if not fields:
                    return None

                # Upsert
                dialogue_entries = updates.get("dialogue_entries")

                await conn.execute("""
                    INSERT INTO image_metadata (shot_id, review_prompt, video_prompt_override,
                        director_notes, dinov2_guideline, dinov2_notes, dialogue_entries,
                        dialogue_text, continuity_prompt, lock_final)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (shot_id) DO UPDATE SET
                        review_prompt = COALESCE(EXCLUDED.review_prompt, image_metadata.review_prompt),
                        video_prompt_override = COALESCE(EXCLUDED.video_prompt_override, image_metadata.video_prompt_override),
                        director_notes = COALESCE(EXCLUDED.director_notes, image_metadata.director_notes),
                        dinov2_guideline = COALESCE(EXCLUDED.dinov2_guideline, image_metadata.dinov2_guideline),
                        dinov2_notes = COALESCE(EXCLUDED.dinov2_notes, image_metadata.dinov2_notes),
                        dialogue_entries = COALESCE(EXCLUDED.dialogue_entries, image_metadata.dialogue_entries),
                        dialogue_text = COALESCE(EXCLUDED.dialogue_text, image_metadata.dialogue_text),
                        continuity_prompt = COALESCE(EXCLUDED.continuity_prompt, image_metadata.continuity_prompt),
                        lock_final = COALESCE(EXCLUDED.lock_final, image_metadata.lock_final),
                        updated_at = CURRENT_TIMESTAMP
                """,
                    shot_id,
                    fields.get("review_prompt"),
                    fields.get("video_prompt_override"),
                    fields.get("director_notes"),
                    fields.get("dinov2_guideline"),
                    fields.get("dinov2_notes"),
                    json.dumps(dialogue_entries) if dialogue_entries else None,
                    fields.get("dialogue_text"),
                    fields.get("continuity_prompt"),
                    fields.get("lock_final"),
                )

                return await self.load_image_metadata(shot_id)
        except Exception as e:
            logger.error(f"Failed to update image metadata: {e}")
            return None


# =============================================================================
# MIGRATION UTILITY
# =============================================================================

async def migrate_json_to_postgres(
    json_path: Path,
    config: Optional[DatabaseConfig] = None
) -> Tuple[int, int]:
    """
    Migrate render_tracking.json to PostgreSQL.
    Returns (shots_migrated, scenes_migrated)
    """
    if not json_path.exists():
        logger.error(f"JSON file not found: {json_path}")
        return 0, 0

    with open(json_path) as f:
        data = json.load(f)

    manager = PostgresGalleryManager(config)
    if not await manager.connect():
        return 0, 0

    shots_migrated = 0
    scenes_migrated = 0

    try:
        # Migrate shots
        for shot_id, shot_data in data.get("shots", {}).items():
            await manager.register_shot(
                shot_id=shot_id,
                scene_id=shot_data.get("scene_id", "UNKNOWN"),
                video_path=shot_data.get("video_path"),
                image_path=shot_data.get("image_path"),
                status=shot_data.get("status", "new"),
                metadata={
                    "project": shot_data.get("project"),
                    "episode": shot_data.get("episode"),
                    **shot_data.get("metadata", {})
                }
            )
            shots_migrated += 1

            if shots_migrated % 100 == 0:
                logger.info(f"Migrated {shots_migrated} shots...")

        # Migrate scene metadata
        for scene_id, scene_data in data.get("scenes", {}).items():
            if scene_data.get("stitched_path"):
                await manager.update_scene_stitch(scene_id, scene_data["stitched_path"])
            scenes_migrated += 1

        logger.info(f"Migration complete: {shots_migrated} shots, {scenes_migrated} scenes")

    finally:
        await manager.close()

    return shots_migrated, scenes_migrated


# =============================================================================
# SYNCHRONOUS WRAPPER (for backwards compatibility)
# =============================================================================

class SyncPostgresGalleryManager:
    """
    Synchronous wrapper for PostgresGalleryManager.
    Used for backwards compatibility with existing code.
    """

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig.from_env()
        self._async_manager = PostgresGalleryManager(config)
        self._loop = None

    def _get_loop(self):
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    def _run(self, coro):
        return self._get_loop().run_until_complete(coro)

    def connect(self) -> bool:
        return self._run(self._async_manager.connect())

    def close(self):
        self._run(self._async_manager.close())

    def register_new_render(self, shot_id: str, video_path: str, image_path: str,
                           scene_id: str, metadata: dict = None, status: str = 'new'):
        self._run(self._async_manager.register_shot(
            shot_id, scene_id, video_path, image_path, status, metadata
        ))

    def mark_shot(self, shot_id: str, status: str):
        self._run(self._async_manager.mark_shot(shot_id, status))

    def get_shot(self, shot_id: str) -> Optional[dict]:
        return self._run(self._async_manager.get_shot(shot_id))

    def get_scene_shots(self, scene_id: str) -> List[str]:
        return self._run(self._async_manager.get_scene_shots(scene_id))

    def is_scene_complete(self, scene_id: str) -> bool:
        return self._run(self._async_manager.is_scene_complete(scene_id))

    def list_projects(self) -> Dict[str, Dict]:
        return self._run(self._async_manager.list_projects())

    def get_all_shots(self, limit: int = 10000) -> List[Dict]:
        """V15.3: Get all shots from database (backwards compatibility)"""
        return self._run(self._async_manager.get_all_shots(limit))

    def get_shots_by_project(self, project: str, scene_id: str = None, limit: int = 1000) -> List[Dict]:
        """V15.3: Get shots filtered by project"""
        return self._run(self._async_manager.get_shots_by_project(project, scene_id, limit))

    def load_image_metadata(self, shot_id: str) -> Optional[dict]:
        return self._run(self._async_manager.load_image_metadata(shot_id))

    def update_image_metadata(self, shot_id: str, updates: dict) -> Optional[dict]:
        return self._run(self._async_manager.update_image_metadata(shot_id, updates))

    @property
    def tracking(self) -> dict:
        """Backwards compatibility - build tracking dict from DB"""
        stats = self._run(self._async_manager.get_stats())
        return {"stats": stats, "shots": {}, "scenes": {}}


if __name__ == "__main__":
    # Test migration
    import sys

    logging.basicConfig(level=logging.INFO)

    json_path = Path("/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/render_tracking.json")

    print("ATLAS PostgreSQL Migration")
    print("=" * 60)
    print(f"Source: {json_path}")
    print()

    # Run migration
    shots, scenes = asyncio.run(migrate_json_to_postgres(json_path))

    print()
    print(f"Migrated: {shots} shots, {scenes} scenes")
