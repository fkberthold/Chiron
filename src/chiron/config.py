"""Configuration management for Chiron."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChironConfig(BaseSettings):
    """Application configuration with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix="CHIRON_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Paths
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".chiron")

    # MCP Server
    mcp_host: str = "localhost"
    mcp_port: int = 8742

    # ChromaDB
    chroma_collection_prefix: str = "chiron"

    # Agent settings
    agent_model: str = "claude-sonnet-4-20250514"
    agent_max_tokens: int = 8192

    @property
    def database_path(self) -> Path:
        """Path to SQLite database."""
        return self.data_dir / "chiron.db"

    @property
    def knowledge_bases_dir(self) -> Path:
        """Directory for subject knowledge bases."""
        return self.data_dir / "knowledge_bases"

    @property
    def lessons_dir(self) -> Path:
        """Directory for generated lessons."""
        return self.data_dir / "lessons"

    @property
    def progress_dir(self) -> Path:
        """Directory for progress tracking files."""
        return self.data_dir / "progress"

    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_bases_dir.mkdir(exist_ok=True)
        self.lessons_dir.mkdir(exist_ok=True)
        self.progress_dir.mkdir(exist_ok=True)


@lru_cache
def get_config() -> ChironConfig:
    """Get cached configuration instance."""
    return ChironConfig()
