"""
ATLAS Run Lock — V37 Regression Guard
======================================
Only verified systems fire. Everything else is blocked.

This module is a GUARD, not a rewrite. It logs and blocks unauthorized
system activations — it never modifies any generation logic itself.

Usage:
    from run_lock import is_system_allowed, get_run_lock_report, reset_run_lock
"""

# The 7 verified systems — ONLY these are allowed to activate
V37_VERIFIED_SYSTEMS = {
    "nano_eshot_frames": True,       # Nano/FAL for E-shot first frames
    "kling_video_gen": True,         # Kling V3 Pro for video
    "chain_propagation": True,       # End-frame → next shot chain
    "vvo_character_bleed": True,     # VVO post-video CHARACTER_BLEED check
    "prompt_decontamination": True,  # CPC decontaminate on all 3 paths
    "chain_intelligence_gate": True, # Pre/post gen arc validation
    "consciousness_controller": True, # Scene consciousness validation
}

# BLOCKED systems — these must NOT activate
V37_BLOCKED_SYSTEMS = {
    "v26_orchestrator": True,         # Legacy V26 routing
    "seedance_pipeline": True,        # Dead Seedance stubs
    "old_frame_reuse": True,          # Pre-V36.4 frame reuse
    "independent_m_frames": True,     # M-shots generating independent frames (chain handles them)
    "duplicate_vvo_preflight": True,  # Redundant VVO at preflight when post-video handles it
}


class RunLock:
    """Enforces V37 verified-only execution."""

    def __init__(self):
        self.active = True
        self.blocked_attempts: list = []

    def check(self, system_name: str) -> bool:
        """Returns True if system is allowed to run. Logs and blocks unauthorized systems."""
        if system_name in V37_VERIFIED_SYSTEMS:
            return True
        if system_name in V37_BLOCKED_SYSTEMS:
            self.blocked_attempts.append(system_name)
            print(f"🔒 RUN LOCK: Blocked activation of '{system_name}' — not in V37 verified set")
            return False
        # Unknown system — block by default, log it
        self.blocked_attempts.append(f"UNKNOWN:{system_name}")
        print(f"🔒 RUN LOCK: Blocked UNKNOWN system '{system_name}' — not verified for V37")
        return False

    def report(self) -> dict:
        """Returns run lock status for the UI."""
        return {
            "lock_active": self.active,
            "verified_count": len(V37_VERIFIED_SYSTEMS),
            "blocked_attempts": self.blocked_attempts,
            "status": "CLEAN" if not self.blocked_attempts else f"BLOCKED {len(self.blocked_attempts)} attempts",
        }


# Global singleton
_run_lock = RunLock()


def is_system_allowed(system_name: str) -> bool:
    return _run_lock.check(system_name)


def get_run_lock_report() -> dict:
    return _run_lock.report()


def reset_run_lock():
    global _run_lock
    _run_lock = RunLock()
