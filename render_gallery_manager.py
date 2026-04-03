#!/usr/bin/env python3
"""
🎬 RENDER GALLERY MANAGER
Shows ALL renders from the beginning, tracks what works, auto-stitches scenes

CRITICAL FEATURES:
1. Real-time render gallery (see every generation)
2. Smart tracking (mark good/bad shots)
3. Auto-stitch completed scenes
4. Review finished scenes
5. Download from FAL before it deletes them (ALREADY DONE in nano_banana_executor.py!)
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import shutil

class RenderGalleryManager:
    """Manages render gallery, tracking, and auto-stitching"""

    def __init__(self, project_root: Path = None):
        if project_root is None:
            # Use relative path from current file location
            project_root = Path(__file__).parent.resolve()

        self.project_root = project_root
        self.output_dir = project_root / "fal_cache"
        self.gallery_dir = self.project_root / "render_gallery"
        self.scenes_dir = self.project_root / "stitched_scenes"
        self.tracking_file = self.project_root / "render_tracking.json"

        # Create directories
        self.gallery_dir.mkdir(exist_ok=True)
        self.scenes_dir.mkdir(exist_ok=True)

        # Load tracking
        self.tracking = self._load_tracking()

        print("="*80)
        print("🎬 RENDER GALLERY MANAGER")
        print("="*80)
        print(f"📂 Output: {self.output_dir}")
        print(f"🖼️  Gallery: {self.gallery_dir}")
        print(f"🎞️  Scenes: {self.scenes_dir}")
        print(f"📊 Tracking: {len(self.tracking.get('shots', {}))} shots tracked")
        print()

    def _load_tracking(self) -> dict:
        """Load render tracking JSON"""
        if self.tracking_file.exists():
            with open(self.tracking_file) as f:
                data = json.load(f)
        else:
            data = {
                'shots': {},
                'scenes': {},
                'stats': {}
            }

        stats = data.setdefault('stats', {})
        stats.setdefault('total_generated', 0)
        stats.setdefault('working', 0)
        stats.setdefault('needs_regen', 0)
        stats.setdefault('ready_for_video', 0)
        stats.setdefault('image_pending', 0)
        stats.setdefault('scenes_stitched', 0)

        data.setdefault('shots', {})
        data.setdefault('scenes', {})
        return data

    def _save_tracking(self):
        """Save render tracking JSON"""
        with open(self.tracking_file, 'w') as f:
            json.dump(self.tracking, f, indent=2)

    def _adjust_stats_on_add(self, status: str):
        stats = self.tracking['stats']
        if status == 'new':
            stats['total_generated'] += 1
        elif status == 'working':
            stats['working'] += 1
        elif status == 'needs_regen':
            stats['needs_regen'] += 1
        elif status == 'ready_for_video':
            stats['ready_for_video'] += 1
        elif status == 'image_pending_video':
            stats['image_pending'] += 1

    def _adjust_stats_on_remove(self, status: str):
        stats = self.tracking['stats']
        if status == 'new' and stats['total_generated'] > 0:
            stats['total_generated'] -= 1
        elif status == 'working' and stats['working'] > 0:
            stats['working'] -= 1
        elif status == 'needs_regen' and stats['needs_regen'] > 0:
            stats['needs_regen'] -= 1
        elif status == 'ready_for_video' and stats['ready_for_video'] > 0:
            stats['ready_for_video'] -= 1
        elif status == 'image_pending_video' and stats['image_pending'] > 0:
            stats['image_pending'] -= 1

    def register_new_render(
        self,
        shot_id: str,
        video_path: str,
        image_path: str,
        scene_id: str,
        metadata: dict = None,
        status: str = 'new'
    ):
        """
        Register a newly generated render

        CALLED IMMEDIATELY after generation in nano_banana_executor.py
        """
        timestamp = datetime.now().isoformat()

        previous = self.tracking['shots'].get(shot_id)
        if previous:
            self._adjust_stats_on_remove(previous.get('status', ''))

        # Derive discovery metadata when available
        project_name = None
        episode_name = None
        scene_title = None
        if metadata:
            project_name = metadata.get('project') or metadata.get('series')
            episode_name = metadata.get('episode')
            scene_title = metadata.get('scene_title')

        # Add to tracking
        self.tracking['shots'][shot_id] = {
            'status': status,
            'video_path': str(video_path) if video_path else None,
            'image_path': str(image_path) if image_path else None,
            'scene_id': scene_id,
            'timestamp': timestamp,
            'project': project_name,
            'episode': episode_name,
            'metadata': metadata or {}
        }

        # Update scene tracking
        if scene_id not in self.tracking['scenes']:
            self.tracking['scenes'][scene_id] = {
                'shots': [],
                'stitched_path': None,
                'status': 'in_progress',
                'project': project_name,
                'scene_title': scene_title,
                'episode': episode_name
            }
        else:
            if project_name and not self.tracking['scenes'][scene_id].get('project'):
                self.tracking['scenes'][scene_id]['project'] = project_name
            if scene_title and not self.tracking['scenes'][scene_id].get('scene_title'):
                self.tracking['scenes'][scene_id]['scene_title'] = scene_title
            if episode_name and not self.tracking['scenes'][scene_id].get('episode'):
                self.tracking['scenes'][scene_id]['episode'] = episode_name

        if shot_id not in self.tracking['scenes'][scene_id]['shots']:
            self.tracking['scenes'][scene_id]['shots'].append(shot_id)

        # Update stats
        self._adjust_stats_on_add(status)

        self._save_tracking()

        print(f"   📌 REGISTERED: {shot_id}")
        print(f"      Scene: {scene_id}")
        video_display = Path(video_path).name if video_path else "(pending)"
        print(f"      Video: {video_display}")
        if image_path:
            print(f"      Image: {Path(image_path).name}")

    def mark_shot(self, shot_id: str, status: str):
        """
        Update shot status (working, needs_regen, ready_for_video, image_pending_video, etc.)
        """
        if shot_id not in self.tracking['shots']:
            print(f"   ⚠️  Shot {shot_id} not found in tracking")
            return

        old_status = self.tracking['shots'][shot_id]['status']
        if old_status == status:
            print(f"   ℹ️  Shot {shot_id} already marked {status}")
            return
        self.tracking['shots'][shot_id]['status'] = status

        self._adjust_stats_on_remove(old_status)
        self._adjust_stats_on_add(status)

        self._save_tracking()

        print(f"   ✅ MARKED: {shot_id} as {status}")

    def get_shot(self, shot_id: str) -> Optional[dict]:
        """Return tracking entry for a shot"""
        return self.tracking['shots'].get(shot_id)

    def get_scene_shots(self, scene_id: str) -> List[str]:
        """Get all shot IDs for a scene"""
        if scene_id not in self.tracking['scenes']:
            return []
        return self.tracking['scenes'][scene_id]['shots']

    def list_projects(self) -> Dict[str, Dict[str, set]]:
        """
        Build index of projects with their scenes/episodes for dashboard filtering.
        """
        index: Dict[str, Dict[str, set]] = {}

        for shot_data in self.tracking['shots'].values():
            project = shot_data.get('project') or shot_data.get('metadata', {}).get('project') or "Unassigned"
            scene_id = shot_data.get('scene_id') or "UNKNOWN"
            episode = shot_data.get('episode') or shot_data.get('metadata', {}).get('episode')

            project_entry = index.setdefault(project, {"scenes": set(), "episodes": set()})
            project_entry["scenes"].add(scene_id)
            if episode:
                project_entry["episodes"].add(episode)

        for scene_id, scene_data in self.tracking['scenes'].items():
            project = scene_data.get('project') or "Unassigned"
            episode = scene_data.get('episode')
            project_entry = index.setdefault(project, {"scenes": set(), "episodes": set()})
            project_entry["scenes"].add(scene_id)
            if episode:
                project_entry["episodes"].add(episode)

        return index

    def is_scene_complete(self, scene_id: str) -> bool:
        """Check if all shots in scene are marked as 'working'"""
        shots = self.get_scene_shots(scene_id)
        if not shots:
            return False

        for shot_id in shots:
            if shot_id not in self.tracking['shots']:
                return False
            if self.tracking['shots'][shot_id]['status'] != 'working':
                return False

        return True

    def auto_stitch_scene(self, scene_id: str, force: bool = False):
        """
        Auto-stitch scene when all shots are 'working'

        Uses ffmpeg concat demuxer for seamless stitching
        """
        if not force and not self.is_scene_complete(scene_id):
            print(f"   ⏳ SCENE {scene_id}: Not ready for stitching (some shots not marked 'working')")
            return None

        shots = self.get_scene_shots(scene_id)
        if not shots:
            print(f"   ⚠️  SCENE {scene_id}: No shots found")
            return None

        print(f"\n🎞️  AUTO-STITCHING SCENE {scene_id}")
        print("="*60)

        # Get video paths in order
        video_paths = []
        for shot_id in sorted(shots):  # Sort to maintain shot order
            shot_data = self.tracking['shots'][shot_id]
            video_path = Path(shot_data['video_path'])

            if not video_path.exists():
                print(f"   ⚠️  Missing: {shot_id} at {video_path}")
                continue

            video_paths.append(video_path)
            print(f"   ✅ {shot_id}: {video_path.name}")

        if not video_paths:
            print(f"   ❌ No valid video files found")
            return None

        # Create concat file for ffmpeg
        concat_file = self.scenes_dir / f"{scene_id}_concat.txt"
        with open(concat_file, 'w') as f:
            for video_path in video_paths:
                f.write(f"file '{video_path.absolute()}'\n")

        # Output path
        output_path = self.scenes_dir / f"{scene_id}_STITCHED.mp4"

        # Stitch with ffmpeg (concat demuxer for seamless stitching)
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(concat_file),
            '-c', 'copy',  # Copy codec (no re-encoding for speed)
            '-y',  # Overwrite
            str(output_path)
        ]

        print(f"\n   🔨 Stitching {len(video_paths)} shots...")

        try:
            subprocess.run(cmd, check=True, capture_output=True)

            # Update tracking
            self.tracking['scenes'][scene_id]['stitched_path'] = str(output_path)
            self.tracking['scenes'][scene_id]['status'] = 'complete'
            self.tracking['stats']['scenes_stitched'] += 1
            self._save_tracking()

            # Get file size
            size_mb = output_path.stat().st_size / (1024 * 1024)

            print(f"\n   ✅ STITCHED: {output_path.name}")
            print(f"      Size: {size_mb:.2f} MB")
            print(f"      Shots: {len(video_paths)}")

            # Clean up concat file
            concat_file.unlink()

            return output_path

        except subprocess.CalledProcessError as e:
            print(f"   ❌ Stitching failed: {e}")
            print(f"      stderr: {e.stderr.decode()}")
        return None

    def review_scene(self, scene_id: str):
        """Open stitched scene for review in QuickTime/default player"""
        if scene_id not in self.tracking['scenes']:
            print(f"   ⚠️  Scene {scene_id} not found")
            return

        stitched_path = self.tracking['scenes'][scene_id].get('stitched_path')
        if not stitched_path or not Path(stitched_path).exists():
            print(f"   ⚠️  Scene {scene_id} not stitched yet")
            return

        print(f"\n🎬 OPENING SCENE {scene_id} FOR REVIEW")
        print(f"   Path: {stitched_path}")

        # Open with default video player
        subprocess.run(['open', stitched_path])

    def show_gallery(self, scene_id: str = None):
        """Show render gallery for all shots or specific scene"""
        print("\n🖼️  RENDER GALLERY")
        print("="*80)

        if scene_id:
            shots = self.get_scene_shots(scene_id)
            print(f"Scene: {scene_id} ({len(shots)} shots)")
        else:
            shots = list(self.tracking['shots'].keys())
            print(f"All shots ({len(shots)} total)")

        print()

        for shot_id in sorted(shots):
            shot_data = self.tracking['shots'][shot_id]
            status = shot_data['status']
            video_path_raw = shot_data.get('video_path')
            video_path = Path(video_path_raw) if video_path_raw else None
            status_emoji = {
                'new': '🆕',
                'working': '✅',
                'needs_regen': '❌',
                'ready_for_video': '🚀',
                'image_pending_video': '🎨'
            }.get(status, '❓')

            if status == 'image_pending_video':
                exists = '🖼️ '
            else:
                exists = '📹' if video_path and video_path.exists() else '⚠️ '

            print(f"{status_emoji} {exists} {shot_id}")
            print(f"   Status: {status}")
            if video_path:
                print(f"   Video: {video_path.name}")
            else:
                print(f"   Video: (pending)")
            image_path = shot_data.get('image_path')
            if image_path:
                print(f"   Image: {Path(image_path).name}")
            print(f"   Timestamp: {shot_data['timestamp']}")
            print()

    def _metadata_path_for(self, shot_id: str) -> Optional[Path]:
        shot = self.tracking['shots'].get(shot_id)
        if not shot:
            # Still check default location even if not in tracking
            default_path = self.output_dir.parent / "render_gallery" / "image_metadata" / f"{shot_id}.json"
            if default_path.exists():
                return default_path
            return None
        meta_path = shot.get('metadata', {}).get('metadata_path')
        if meta_path:
            return Path(meta_path)
        # Fallback to default location
        default_path = self.output_dir.parent / "render_gallery" / "image_metadata" / f"{shot_id}.json"
        if default_path.exists():
            return default_path
        return None

    def load_image_metadata(self, shot_id: str) -> Optional[dict]:
        """Load stored metadata for a shot image if available"""
        meta_path = self._metadata_path_for(shot_id)
        if not meta_path or not meta_path.exists():
            return None
        try:
            with meta_path.open() as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"   ⚠️  Corrupted metadata for {shot_id}: {meta_path}")
            return None

    def update_image_metadata(self, shot_id: str, updates: dict) -> Optional[dict]:
        """
        Apply updates to stored metadata (non-destructive merge).
        Returns updated metadata dict or None if shot missing.
        """
        meta_path = self._metadata_path_for(shot_id)
        if not meta_path:
            print(f"   ⚠️  Metadata path missing for {shot_id}")
            return None
        current = {}
        if meta_path.exists():
            try:
                current = json.loads(meta_path.read_text())
            except json.JSONDecodeError:
                print(f"   ⚠️  Corrupted metadata for {shot_id}, replacing")
        current.update(updates)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(current, indent=2))
        print(f"   💾 Metadata updated for {shot_id} ({meta_path})")
        return current

    def show_stats(self):
        """Show render statistics"""
        stats = self.tracking['stats']

        print("\n📊 RENDER STATISTICS")
        print("="*80)
        print(f"Total Generated: {stats['total_generated']}")
        print(f"Working: {stats['working']}")
        print(f"Needs Regen: {stats['needs_regen']}")
        print(f"Ready For Video: {stats['ready_for_video']}")
        print(f"Image Pending Video: {stats['image_pending']}")
        print(f"Scenes Stitched: {stats['scenes_stitched']}")
        print()

        print("SCENES:")
        for scene_id, scene_data in self.tracking['scenes'].items():
            status = scene_data['status']
            shot_count = len(scene_data['shots'])
            stitched = '🎞️ ' if scene_data.get('stitched_path') else '⏳'

            print(f"  {stitched} {scene_id}: {shot_count} shots ({status})")


def main():
    """Demo usage"""
    manager = RenderGalleryManager()

    # Show current gallery
    manager.show_gallery()
    manager.show_stats()

    # Check for complete scenes and auto-stitch
    print("\n🔍 CHECKING FOR COMPLETE SCENES...")
    for scene_id in manager.tracking['scenes'].keys():
        if manager.is_scene_complete(scene_id):
            print(f"\n✅ Scene {scene_id} is complete - auto-stitching...")
            output_path = manager.auto_stitch_scene(scene_id)
            if output_path:
                manager.review_scene(scene_id)


if __name__ == '__main__':
    main()
