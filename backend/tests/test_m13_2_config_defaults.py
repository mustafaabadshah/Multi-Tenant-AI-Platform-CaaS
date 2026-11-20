"""M13.2 configuration foundation: safe defaults and API docs gating."""

from app.core.config import Settings, api_docs_enabled

MIB = 1024 * 1024


def _settings(**overrides) -> Settings:
    """Build settings without reading a developer-local .env file."""
    return Settings(_env_file=None, **overrides)


def test_safe_feature_flag_defaults():
    cfg = _settings()
    assert cfg.PUBLIC_PUBLISHING_ENABLED is False
    assert cfg.DEVELOPER_API_ENABLED is False
    assert cfg.CUSTOM_PROVIDER_ENDPOINTS_ENABLED is False


def test_upload_and_ingestion_defaults():
    cfg = _settings()
    assert cfg.MAX_FILE_SIZE_BYTES == 10 * MIB
    assert cfg.MAX_FILES_PER_REQUEST == 2
    assert cfg.MAX_EXTRACTED_TEXT_SIZE_BYTES == 5 * MIB
    assert cfg.INGESTION_MAX_CONCURRENCY == 1
    assert cfg.OCR_ENABLED_DEFAULT is False


def test_api_docs_enabled_derives_from_environment():
    assert api_docs_enabled(_settings(ENVIRONMENT="development")) is True
    assert api_docs_enabled(_settings(ENVIRONMENT="staging")) is False
    assert api_docs_enabled(_settings(ENVIRONMENT="production")) is False


def test_api_docs_enabled_explicit_override():
    assert api_docs_enabled(_settings(ENVIRONMENT="production", ENABLE_API_DOCS=True)) is True
    assert api_docs_enabled(_settings(ENVIRONMENT="development", ENABLE_API_DOCS=False)) is False


def test_settings_accepts_feature_flags():
    cfg = _settings(
        PUBLIC_PUBLISHING_ENABLED=True,
        DEVELOPER_API_ENABLED=True,
        CUSTOM_PROVIDER_ENDPOINTS_ENABLED=True,
    )
    assert cfg.PUBLIC_PUBLISHING_ENABLED is True
    assert cfg.DEVELOPER_API_ENABLED is True
    assert cfg.CUSTOM_PROVIDER_ENDPOINTS_ENABLED is True
