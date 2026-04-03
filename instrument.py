#!/usr/bin/env python3
"""
ATLAS Sentry Instrumentation - MUST be imported FIRST
=====================================================
Captures all errors, warnings, and bad states for debugging.

V17: In LOCKED mode, Sentry MUST be initialized or startup fails.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env BEFORE reading SENTRY_DSN
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration

# V17: Check execution mode
EXECUTION_MODE = os.getenv("ATLAS_MODE", "dev")
SENTRY_DSN = os.getenv("SENTRY_DSN")

# V17: LOCKED mode requires Sentry
if EXECUTION_MODE == "LOCKED" and not SENTRY_DSN:
    print("=" * 60)
    print("FATAL: LOCKED mode requires SENTRY_DSN to be configured!")
    print("Set SENTRY_DSN in .env or disable LOCKED mode.")
    print("=" * 60)
    sys.exit(1)

# Logging integration - capture logs as breadcrumbs
logging_integration = LoggingIntegration(
    level=None,          # Capture info logs as breadcrumbs
    event_level=None     # Don't auto-send logs as errors
)

# Initialize Sentry
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            logging_integration,
            FastApiIntegration(),
        ],

        # Performance monitoring
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,

        # Environment and release
        environment=os.getenv("ENV", "dev"),
        release="atlas@" + os.getenv("ATLAS_VERSION", "17.0.0"),

        # Privacy
        send_default_pii=False,

        # Attach request data
        attach_stacktrace=True,
    )
    print(f"[SENTRY] Instrumentation initialized (mode: {EXECUTION_MODE})")
else:
    print(f"[SENTRY] WARNING: Not initialized - errors will not be captured (mode: {EXECUTION_MODE})")


def is_sentry_active() -> bool:
    """Check if Sentry is actively capturing errors."""
    hub = sentry_sdk.Hub.current
    return hub.client is not None and hub.client.dsn is not None


def require_sentry():
    """Call this in LOCKED mode operations to ensure Sentry is active."""
    if not is_sentry_active():
        raise RuntimeError("LOCKED mode operation requires active Sentry instrumentation")
