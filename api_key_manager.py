#!/usr/bin/env python3
"""
🔑 API Key Manager - Parallel API Key Rotation System
Distributes API calls across multiple Replicate keys for 7x speedup
"""
import time
from typing import List, Optional, Dict
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class APIKeyManager:
    """
    Manages multiple Replicate API keys for parallel processing
    Round-robin distribution with usage tracking
    """

    def __init__(self, keys: List[str] = None):
        """Initialize with list of API keys"""
        if keys is None:
            # All 7 Replicate API keys
            keys = [
                os.environ.get("REPLICATE_TOKEN_1", ""),
                os.environ.get("REPLICATE_TOKEN_2", ""),
                os.environ.get("REPLICATE_TOKEN_3", ""),
                os.environ.get("REPLICATE_TOKEN_4", ""),
                os.environ.get("REPLICATE_TOKEN_5", ""),
                os.environ.get("REPLICATE_TOKEN_6", ""),
                os.environ.get("REPLICATE_TOKEN_7", "")
            ]

        self.keys = keys
        self.current_index = 0
        self.lock = Lock()

        # Usage tracking
        self.usage_stats = {key: {'calls': 0, 'errors': 0, 'last_used': 0} for key in keys}

        logger.info(f"🔑 API Key Manager initialized with {len(keys)} keys")

    def get_next_key(self) -> str:
        """Get next key in round-robin fashion"""
        with self.lock:
            key = self.keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.keys)

            # Update usage stats
            self.usage_stats[key]['calls'] += 1
            self.usage_stats[key]['last_used'] = time.time()

            logger.debug(f"🔑 Assigned key #{self.current_index}: ...{key[-6:]}")
            return key

    def report_error(self, key: str):
        """Report an error for a specific key"""
        with self.lock:
            if key in self.usage_stats:
                self.usage_stats[key]['errors'] += 1
                logger.warning(f"⚠️ Error reported for key ...{key[-6:]}")

    def get_key_for_task(self, task_id: int) -> str:
        """
        Get a specific key for a task ID (for parallel distribution)
        Allows multiple tasks to run concurrently with different keys
        """
        key_index = task_id % len(self.keys)
        key = self.keys[key_index]

        with self.lock:
            self.usage_stats[key]['calls'] += 1
            self.usage_stats[key]['last_used'] = time.time()

        logger.debug(f"🔑 Task {task_id} assigned key #{key_index}: ...{key[-6:]}")
        return key

    def get_statistics(self) -> Dict:
        """Get usage statistics for all keys"""
        with self.lock:
            stats = {
                'total_keys': len(self.keys),
                'total_calls': sum(s['calls'] for s in self.usage_stats.values()),
                'total_errors': sum(s['errors'] for s in self.usage_stats.values()),
                'keys': []
            }

            for i, key in enumerate(self.keys):
                key_stats = self.usage_stats[key]
                stats['keys'].append({
                    'index': i,
                    'key_suffix': key[-6:],
                    'calls': key_stats['calls'],
                    'errors': key_stats['errors'],
                    'error_rate': key_stats['errors'] / max(key_stats['calls'], 1),
                    'last_used': key_stats['last_used']
                })

            return stats

    def print_statistics(self):
        """Print formatted usage statistics"""
        stats = self.get_statistics()

        print("\n" + "="*70)
        print("🔑 API KEY USAGE STATISTICS")
        print("="*70)
        print(f"Total Keys: {stats['total_keys']}")
        print(f"Total Calls: {stats['total_calls']}")
        print(f"Total Errors: {stats['total_errors']}")
        print(f"Average Calls per Key: {stats['total_calls'] / stats['total_keys']:.1f}")
        print("\nPer-Key Breakdown:")
        print("-"*70)
        print(f"{'Key':<8} {'Calls':<8} {'Errors':<8} {'Error Rate':<12} {'Status'}")
        print("-"*70)

        for key_stat in stats['keys']:
            status = "✅" if key_stat['error_rate'] < 0.1 else "⚠️" if key_stat['error_rate'] < 0.3 else "❌"
            print(f"...{key_stat['key_suffix']:<6} {key_stat['calls']:<8} "
                  f"{key_stat['errors']:<8} {key_stat['error_rate']:<12.1%} {status}")

        print("="*70 + "\n")

    def reset_statistics(self):
        """Reset all usage statistics"""
        with self.lock:
            for key in self.keys:
                self.usage_stats[key] = {'calls': 0, 'errors': 0, 'last_used': 0}
            self.current_index = 0
        logger.info("📊 Statistics reset")


# Global API key manager
_api_key_manager = None

def get_api_key_manager() -> APIKeyManager:
    """Get or create global API key manager"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def get_next_replicate_key() -> str:
    """Convenience function to get next key"""
    return get_api_key_manager().get_next_key()


def get_key_for_scene(scene_number: int) -> str:
    """Get key for a specific scene number (enables parallel rendering)"""
    return get_api_key_manager().get_key_for_task(scene_number)


if __name__ == "__main__":
    # Test API key manager
    logging.basicConfig(level=logging.INFO)

    manager = APIKeyManager()

    print("\n🧪 Testing API Key Rotation...\n")

    # Simulate 20 API calls
    print("Simulating 20 sequential calls:")
    for i in range(20):
        key = manager.get_next_key()
        print(f"  Call {i+1}: ...{key[-6:]}")

    # Simulate parallel tasks
    print("\nSimulating 10 parallel tasks:")
    for task_id in range(10):
        key = manager.get_key_for_task(task_id)
        print(f"  Task {task_id}: ...{key[-6:]}")

    # Simulate some errors
    print("\nSimulating errors on 3 keys:")
    for i in range(3):
        key = manager.keys[i]
        manager.report_error(key)
        print(f"  Error on key ...{key[-6:]}")

    # Print statistics
    manager.print_statistics()

    print("✅ API Key Manager test complete")
