#!/usr/bin/env python3
"""
SAFE I/O UTILITIES

Atomic writes, rate limiting, and thread-safe operations for ATLAS.

Usage:
    from tools.safe_io import atomic_write_json, RateLimiter
"""

import json
import os
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from functools import wraps


# =============================================================================
# ATOMIC JSON WRITES
# =============================================================================

def atomic_write_json(path: Path, data: Dict, indent: int = 2) -> bool:
    """
    Atomically write JSON to file.

    Writes to temp file first, then renames (atomic on POSIX).
    Prevents partial writes during turbo parallel operations.
    """
    path = Path(path)
    temp_path = path.with_suffix('.tmp')

    try:
        # Write to temp file
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=indent)
            f.flush()
            os.fsync(f.fileno())

        # Atomic rename
        temp_path.rename(path)
        return True

    except Exception as e:
        # Cleanup temp file on failure
        if temp_path.exists():
            temp_path.unlink()
        raise e


def safe_read_json(path: Path, default: Dict = None) -> Dict:
    """
    Safely read JSON with fallback to default.
    Handles missing files and parse errors gracefully.
    """
    path = Path(path)

    if not path.exists():
        return default if default is not None else {}

    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default if default is not None else {}


# =============================================================================
# RATE LIMITER WITH BACKOFF
# =============================================================================

class RateLimiter:
    """
    Thread-safe rate limiter with exponential backoff.

    Usage:
        limiter = RateLimiter(max_per_second=5)

        def worker():
            limiter.acquire()  # Blocks if rate exceeded
            make_api_call()
    """

    def __init__(self, max_per_second: float = 5.0, max_backoff: float = 60.0):
        self.max_per_second = max_per_second
        self.min_interval = 1.0 / max_per_second
        self.max_backoff = max_backoff
        self.lock = threading.Lock()
        self.last_call = 0.0
        self.consecutive_errors = 0
        self.backoff_until = 0.0

    def acquire(self):
        """Acquire rate limit slot, blocking if necessary."""
        with self.lock:
            now = time.time()

            # Check if in backoff period
            if now < self.backoff_until:
                wait_time = self.backoff_until - now
                time.sleep(wait_time)
                now = time.time()

            # Enforce minimum interval
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)

            self.last_call = time.time()

    def report_success(self):
        """Report successful call to reset backoff."""
        with self.lock:
            self.consecutive_errors = 0
            self.backoff_until = 0.0

    def report_error(self, is_rate_limit: bool = False):
        """Report error, increasing backoff if rate-limited."""
        with self.lock:
            self.consecutive_errors += 1

            if is_rate_limit:
                # Exponential backoff: 1s, 2s, 4s, 8s, ... up to max
                backoff = min(2 ** self.consecutive_errors, self.max_backoff)
                self.backoff_until = time.time() + backoff
                return backoff

            return 0

    def get_stats(self) -> Dict:
        """Get current limiter stats."""
        with self.lock:
            return {
                "consecutive_errors": self.consecutive_errors,
                "backoff_until": self.backoff_until,
                "in_backoff": time.time() < self.backoff_until
            }


# =============================================================================
# THREAD-SAFE COUNTER
# =============================================================================

class AtomicCounter:
    """Thread-safe counter for tracking parallel operations."""

    def __init__(self, initial: int = 0):
        self.value = initial
        self.lock = threading.Lock()

    def increment(self, amount: int = 1) -> int:
        with self.lock:
            self.value += amount
            return self.value

    def decrement(self, amount: int = 1) -> int:
        with self.lock:
            self.value -= amount
            return self.value

    def get(self) -> int:
        with self.lock:
            return self.value

    def set(self, value: int):
        with self.lock:
            self.value = value


# =============================================================================
# PROJECT LOCK
# =============================================================================

class ProjectLock:
    """
    Project-level lock to prevent concurrent writes.

    Usage:
        lock = ProjectLock()

        with lock.acquire("kord_v17"):
            modify_shot_plan()
    """

    def __init__(self):
        self.locks: Dict[str, threading.Lock] = {}
        self.meta_lock = threading.Lock()

    def _get_lock(self, project: str) -> threading.Lock:
        with self.meta_lock:
            if project not in self.locks:
                self.locks[project] = threading.Lock()
            return self.locks[project]

    def acquire(self, project: str):
        """Context manager for project lock."""
        return self._get_lock(project)

    def is_locked(self, project: str) -> bool:
        with self.meta_lock:
            if project not in self.locks:
                return False
            return self.locks[project].locked()


# Global instances
_rate_limiter = RateLimiter(max_per_second=10)
_project_locks = ProjectLock()


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter."""
    return _rate_limiter


def get_project_lock() -> ProjectLock:
    """Get global project lock manager."""
    return _project_locks


# =============================================================================
# RETRY DECORATOR
# =============================================================================

def with_retry(max_attempts: int = 3, backoff_base: float = 1.0, rate_limiter: RateLimiter = None):
    """
    Decorator for retrying functions with exponential backoff.

    Usage:
        @with_retry(max_attempts=3)
        def call_api():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter = rate_limiter or get_rate_limiter()
            last_error = None

            for attempt in range(max_attempts):
                try:
                    limiter.acquire()
                    result = func(*args, **kwargs)
                    limiter.report_success()
                    return result

                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()
                    is_rate_limit = "429" in error_str or "rate" in error_str

                    backoff = limiter.report_error(is_rate_limit)

                    if attempt < max_attempts - 1:
                        wait = backoff if is_rate_limit else backoff_base * (2 ** attempt)
                        time.sleep(wait)

            raise last_error

        return wrapper
    return decorator
