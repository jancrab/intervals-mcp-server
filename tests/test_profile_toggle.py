"""v1.5.0 — lean promotions + the full_toolset boolean toggle."""

from intervals_mcp_server.config import load_config
from intervals_mcp_server.tools.profile import LEAN_TOOLS


def test_gear_and_ftp_tools_promoted_to_lean():
    """v1.5.0 puts the recurring gear-maintenance + FTP-set ops in lean so
    they work without a full escalation."""
    for tool in (
        "update_sport_settings",
        "create_gear",
        "create_gear_reminder",
        "replace_gear",
        "recalc_gear_distance",
    ):
        assert tool in LEAN_TOOLS, f"{tool} should be lean as of v1.5.0"


def test_get_fitness_model_events_is_full_only():
    """The new read tool stays full-only (rare analytics)."""
    assert "get_fitness_model_events" not in LEAN_TOOLS


def test_profile_defaults_to_lean(monkeypatch):
    monkeypatch.delenv("INTERVALS_PROFILE_FULL", raising=False)
    monkeypatch.delenv("INTERVALS_PROFILE", raising=False)
    assert load_config().profile == "lean"


def test_full_toolset_boolean_truthy_gives_full(monkeypatch):
    monkeypatch.delenv("INTERVALS_PROFILE", raising=False)
    for val in ("true", "True", "TRUE", "1", "yes", "on"):
        monkeypatch.setenv("INTERVALS_PROFILE_FULL", val)
        assert load_config().profile == "full", f"{val!r} should map to full"


def test_full_toolset_boolean_falsy_gives_lean(monkeypatch):
    monkeypatch.delenv("INTERVALS_PROFILE", raising=False)
    for val in ("false", "False", "0", "no", ""):
        monkeypatch.setenv("INTERVALS_PROFILE_FULL", val)
        assert load_config().profile == "lean", f"{val!r} should map to lean"


def test_legacy_profile_full_still_works(monkeypatch):
    """Back-compat: the free-text INTERVALS_PROFILE=full path is preserved."""
    monkeypatch.delenv("INTERVALS_PROFILE_FULL", raising=False)
    monkeypatch.setenv("INTERVALS_PROFILE", "full")
    assert load_config().profile == "full"


def test_toggle_wins_over_legacy_freetext(monkeypatch):
    """If the checkbox is ON it overrides a legacy 'lean' free-text value."""
    monkeypatch.setenv("INTERVALS_PROFILE", "lean")
    monkeypatch.setenv("INTERVALS_PROFILE_FULL", "true")
    assert load_config().profile == "full"
