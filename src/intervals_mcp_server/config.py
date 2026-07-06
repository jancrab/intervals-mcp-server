"""
Configuration management for Intervals.icu MCP Server.

This module handles loading and validation of configuration from environment variables.
"""

import os
from dataclasses import dataclass

from intervals_mcp_server.utils.validation import validate_athlete_id

# Try to load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv

    _ = load_dotenv()
except ImportError:
    # python-dotenv not installed, proceed without it
    pass


@dataclass
class Config:
    """Configuration settings for the Intervals.icu MCP Server."""

    api_key: str
    athlete_id: str
    intervals_api_base_url: str
    user_agent: str
    profile: str  # "lean" (default, ~26 tools) or "full" (all 133 tools)


_config_instance: Config | None = None  # pylint: disable=invalid-name


def load_config() -> Config:
    """
    Load configuration from environment variables.

    Returns:
        Config: Configuration instance with loaded values.

    Raises:
        ValueError: If athlete_id is invalid (when non-empty).
    """
    api_key = os.getenv("API_KEY", "")
    athlete_id = os.getenv("ATHLETE_ID", "")
    intervals_api_base_url = os.getenv("INTERVALS_API_BASE_URL", "https://intervals.icu/api/v1")
    user_agent = "intervalsicu-mcp-server/1.0"

    # Profile gate. "lean" (default, ~45 tools) keeps context cost low for
    # Claude Desktop installs; "full" (all 135 tools) is for occasional
    # advanced modes (gear setup, bulk events, analytics deep-dives).
    #
    # Two inputs; the boolean toggle wins:
    # - INTERVALS_PROFILE_FULL — boolean from the MCPB `full_toolset`
    #   user-config checkbox (passed as "true"/"false"). Truthy → full. This
    #   is the click-based UX; flipping it relaunches the extension server, so
    #   the fresh connect re-reads the tool list (no live mid-session switch).
    # - INTERVALS_PROFILE — legacy free-text ("full" → full), kept for
    #   back-compat and manual/env use.
    # Anything else → lean, so a misspelling never accidentally exposes the
    # full ~135-tool surface.
    profile_full = os.getenv("INTERVALS_PROFILE_FULL", "").strip().lower() in ("true", "1", "yes", "on")
    profile_raw = os.getenv("INTERVALS_PROFILE", "lean").strip().lower()
    profile = "full" if (profile_full or profile_raw == "full") else "lean"

    # Validate athlete_id if provided (empty string is allowed)
    if athlete_id:
        validate_athlete_id(athlete_id)

    return Config(
        api_key=api_key,
        athlete_id=athlete_id,
        intervals_api_base_url=intervals_api_base_url,
        user_agent=user_agent,
        profile=profile,
    )


def get_config() -> Config:
    """
    Get the configuration instance (singleton pattern).

    Returns:
        Config: The configuration instance.
    """
    global _config_instance  # pylint: disable=global-statement  # noqa: PLW0603 - singleton pattern
    if _config_instance is None:
        _config_instance = load_config()
    return _config_instance
