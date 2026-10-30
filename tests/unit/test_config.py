from src.core.config import Settings, get_settings


def test_settings_load_successfully():
    """Verify that settings are instantiated with valid types."""
    settings = get_settings()

    assert isinstance(settings, Settings)
    assert settings.PROJECT_NAME != ""
    assert settings.EMBEDDING_DIMENSION == 768
    assert settings.ACTIVE_EMBEDDING_MODEL == "gemini-embedding-001"
    assert "asyncpg" in settings.DATABASE_URL


def test_supabase_url_normalization():
    """Verify that postgresql:// and sslmode=require are correctly transformed for asyncpg."""
    raw_url = "postgresql://postgres.test:secret@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require"
    converted = Settings.assemble_async_db_url(raw_url)
    assert converted.startswith("postgresql+asyncpg://")
    assert "sslmode=require" not in converted
    assert "ssl=require" in converted
