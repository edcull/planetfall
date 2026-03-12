"""Application configuration — loads from .env file and environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def get_api_key() -> str:
    """Return the Anthropic API key from environment."""
    return os.environ.get("ANTHROPIC_API_KEY", "")


def get_narrative_model() -> str:
    """Return the Claude model to use for scene narration (longer prose)."""
    return os.environ.get("NARRATIVE_MODEL", "claude-sonnet-4-20250514")


def get_background_model() -> str:
    """Return the Claude model to use for character background generation (short text)."""
    return os.environ.get("BACKGROUND_MODEL", "claude-haiku-4-5-20251001")


def get_orchestrator_mode() -> str:
    """Return orchestrator mode: 'api', 'local', or 'hybrid'.

    - api: Claude drives all 18 steps via tool_use (slow, most narrative).
    - local: Pure Python loop, template narrative (fastest, no API calls).
    - hybrid: Local mechanics + Claude API for narrative at key moments (fast + immersive).
    """
    return os.environ.get("ORCHESTRATOR_MODE", "hybrid").lower()


def get_hybrid_narrative_model() -> str:
    """Return the fast model used for hybrid-mode narrative (short bursts)."""
    return os.environ.get("HYBRID_NARRATIVE_MODEL", "claude-haiku-4-5-20251001")


def get_manual_dice() -> bool:
    """Return whether manual dice mode is enabled by default."""
    return os.environ.get("MANUAL_DICE", "false").lower() in ("true", "1", "yes")
