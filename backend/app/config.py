from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://openalex:openalex@localhost:5432/openalex"
    elasticsearch_url: str = "http://localhost:9200"
    # The API always queries the alias; the indexer builds a new versioned index and swaps it.
    es_index_alias: str = "works"

    openalex_base_url: str = "https://api.openalex.org"
    # OpenAlex now requires a (free) API key once the shared per-IP budget is spent.
    openalex_api_key: str | None = None
    harvest_limit: int = 1000

    # Where the harvester writes / the bootstrap step reads the raw JSONL snapshot.
    snapshot_path: str = "data/works.jsonl.gz"

    insights_cache_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
