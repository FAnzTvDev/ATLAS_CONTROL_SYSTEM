#!/usr/bin/env python3
"""
ATLAS Control System - Database Migration Script
V3.2: Migrates render_tracking.json to PostgreSQL

Usage:
    python3 migrate.py                     # Migrate with default settings
    python3 migrate.py --init              # Initialize database schema only
    python3 migrate.py --verify            # Verify migration integrity
    python3 migrate.py --rollback          # Export PostgreSQL back to JSON
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.postgres_manager import (
    DatabaseConfig,
    PostgresGalleryManager,
    migrate_json_to_postgres,
)


def get_config() -> DatabaseConfig:
    """Get database configuration"""
    return DatabaseConfig.from_env()


def init_database(config: DatabaseConfig) -> bool:
    """Initialize PostgreSQL database with schema"""
    print("Initializing PostgreSQL database...")

    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        print(f"ERROR: Schema file not found: {schema_path}")
        return False

    # Create database if needed
    try:
        # First, connect to postgres database to create atlas_control
        create_db_cmd = [
            "psql",
            "-h", config.host,
            "-p", str(config.port),
            "-U", config.user,
            "-d", "postgres",
            "-c", f"CREATE DATABASE {config.database};"
        ]

        if config.password:
            os.environ["PGPASSWORD"] = config.password

        result = subprocess.run(create_db_cmd, capture_output=True, text=True)
        if "already exists" in result.stderr:
            print(f"  Database '{config.database}' already exists")
        elif result.returncode == 0:
            print(f"  Created database '{config.database}'")
        else:
            # Database might already exist, continue anyway
            pass

        # Apply schema
        apply_schema_cmd = [
            "psql",
            "-h", config.host,
            "-p", str(config.port),
            "-U", config.user,
            "-d", config.database,
            "-f", str(schema_path)
        ]

        result = subprocess.run(apply_schema_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  Schema errors (may be OK if tables exist): {result.stderr[:200]}")
        else:
            print("  Schema applied successfully")

        return True

    except Exception as e:
        print(f"ERROR: Failed to initialize database: {e}")
        return False


async def verify_migration(config: DatabaseConfig, json_path: Path) -> dict:
    """Verify migration integrity by comparing counts"""
    print("\nVerifying migration...")

    # Load JSON
    with open(json_path) as f:
        json_data = json.load(f)

    json_shots = len(json_data.get("shots", {}))
    json_scenes = len(json_data.get("scenes", {}))

    # Query PostgreSQL
    manager = PostgresGalleryManager(config)
    if not await manager.connect():
        return {"status": "error", "message": "Failed to connect to PostgreSQL"}

    try:
        async with manager._pool.acquire() as conn:
            db_shots = await conn.fetchval("SELECT COUNT(*) FROM shots")
            db_scenes = await conn.fetchval("SELECT COUNT(*) FROM scenes")

        result = {
            "status": "ok" if db_shots >= json_shots else "incomplete",
            "json_shots": json_shots,
            "json_scenes": json_scenes,
            "db_shots": db_shots,
            "db_scenes": db_scenes,
            "shots_diff": db_shots - json_shots,
            "scenes_diff": db_scenes - json_scenes,
        }

        print(f"  JSON:       {json_shots} shots, {json_scenes} scenes")
        print(f"  PostgreSQL: {db_shots} shots, {db_scenes} scenes")

        if result["status"] == "ok":
            print("  ✅ Migration verified successfully")
        else:
            print("  ⚠️  Some data may not have migrated")

        return result

    finally:
        await manager.close()


async def rollback_to_json(config: DatabaseConfig, output_path: Path) -> bool:
    """Export PostgreSQL data back to JSON format"""
    print(f"\nExporting PostgreSQL to JSON: {output_path}")

    manager = PostgresGalleryManager(config)
    if not await manager.connect():
        return False

    try:
        async with manager._pool.acquire() as conn:
            # Export shots
            shot_rows = await conn.fetch("SELECT * FROM shots ORDER BY shot_id")
            shots = {}
            for row in shot_rows:
                shots[row["shot_id"]] = {
                    "status": row["status"],
                    "video_path": row["video_path"],
                    "image_path": row["image_path"],
                    "scene_id": row["scene_id"],
                    "timestamp": row["created_at"].isoformat() if row["created_at"] else None,
                    "project": row["project"],
                    "episode": row["episode"],
                    "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                }

            # Export scenes
            scene_rows = await conn.fetch("SELECT * FROM scenes ORDER BY scene_id")
            scenes = {}
            for row in scene_rows:
                # Get shot IDs for this scene
                shot_ids = await conn.fetch(
                    "SELECT shot_id FROM shots WHERE scene_id = $1 ORDER BY shot_id",
                    row["scene_id"]
                )
                scenes[row["scene_id"]] = {
                    "shots": [s["shot_id"] for s in shot_ids],
                    "stitched_path": row["stitched_path"],
                    "status": row["status"],
                    "project": row["project"],
                    "episode": row["episode"],
                }

            # Export stats
            stat_rows = await conn.fetch("SELECT stat_key, stat_value FROM render_stats")
            stats = {row["stat_key"]: row["stat_value"] for row in stat_rows}

        # Build output
        output_data = {
            "shots": shots,
            "scenes": scenes,
            "stats": stats,
            "exported_at": datetime.now().isoformat(),
            "source": "postgresql"
        }

        # Write JSON
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"  Exported {len(shots)} shots, {len(scenes)} scenes")
        print(f"  ✅ Saved to: {output_path}")
        return True

    finally:
        await manager.close()


def main():
    parser = argparse.ArgumentParser(description="ATLAS PostgreSQL Migration")
    parser.add_argument("--init", action="store_true", help="Initialize database schema only")
    parser.add_argument("--verify", action="store_true", help="Verify migration integrity")
    parser.add_argument("--rollback", action="store_true", help="Export PostgreSQL back to JSON")
    parser.add_argument("--json-path", type=str,
                       default="/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/render_tracking.json",
                       help="Path to render_tracking.json")
    parser.add_argument("--output", type=str,
                       default="/Users/quantum/Desktop/ATLAS_CONTROL_SYSTEM/render_tracking_export.json",
                       help="Output path for rollback")
    args = parser.parse_args()

    print("=" * 60)
    print("ATLAS Control System - PostgreSQL Migration")
    print("=" * 60)

    config = get_config()
    print(f"\nDatabase: {config.database}@{config.host}:{config.port}")

    json_path = Path(args.json_path)

    if args.init:
        success = init_database(config)
        sys.exit(0 if success else 1)

    if args.verify:
        result = asyncio.run(verify_migration(config, json_path))
        sys.exit(0 if result.get("status") == "ok" else 1)

    if args.rollback:
        success = asyncio.run(rollback_to_json(config, Path(args.output)))
        sys.exit(0 if success else 1)

    # Default: Full migration
    print("\n1. Initializing database...")
    if not init_database(config):
        print("WARNING: Database init had issues, continuing anyway...")

    print("\n2. Migrating data...")
    if not json_path.exists():
        print(f"ERROR: JSON file not found: {json_path}")
        sys.exit(1)

    shots, scenes = asyncio.run(migrate_json_to_postgres(json_path, config))

    print(f"\n3. Migration complete!")
    print(f"   Shots: {shots}")
    print(f"   Scenes: {scenes}")

    # Verify
    print("\n4. Verifying...")
    result = asyncio.run(verify_migration(config, json_path))

    if result.get("status") == "ok":
        print("\n✅ Migration successful!")
        print("\nTo enable PostgreSQL backend, set environment variable:")
        print("  export ATLAS_USE_POSTGRES=1")
    else:
        print("\n⚠️  Migration completed with warnings")


if __name__ == "__main__":
    main()
