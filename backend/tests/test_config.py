"""Phase 0 smoke test: settings load from the environment without error."""

from app.core.config import Settings, get_settings


def test_settings_import_and_construct() -> None:
    settings = Settings()

    assert settings.api_v1_prefix == "/api/v1"
    assert settings.database_url
    assert settings.backend_port > 0


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
