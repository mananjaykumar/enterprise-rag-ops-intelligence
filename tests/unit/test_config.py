from src.core.config import Settings, get_settings


def test_settings_load_successfully():
    """Verify that settings are instantiated with valid types."""
    settings = get_settings()

    assert isinstance(settings, Settings)
    assert settings.PROJECT_NAME != ""
    assert settings.EMBEDDING_DIMENSION == 768
    assert settings.ACTIVE_EMBEDDING_MODEL == "gemini-embedding-001"
    assert "asyncpg" in settings.DATABASE_URL
