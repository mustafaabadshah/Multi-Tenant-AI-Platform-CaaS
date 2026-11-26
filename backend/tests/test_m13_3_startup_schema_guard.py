"""M13.3 startup schema guard: create_all must run only in development."""

from app.core.config import Settings, should_initialize_schema


def _settings(**overrides) -> Settings:
    """Build settings without reading a developer-local .env file."""
    return Settings(_env_file=None, **overrides)


def test_schema_initialization_enabled_in_development():
    assert should_initialize_schema(_settings(ENVIRONMENT="development")) is True


def test_schema_initialization_disabled_in_staging():
    assert should_initialize_schema(_settings(ENVIRONMENT="staging")) is False


def test_schema_initialization_disabled_in_production():
    assert should_initialize_schema(_settings(ENVIRONMENT="production")) is False