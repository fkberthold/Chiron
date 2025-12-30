"""Entry point for running the MCP server standalone."""

from chiron.config import get_config
from chiron.mcp_server.server import create_mcp_server
from chiron.storage.database import Database
from chiron.storage.vector_store import VectorStore


def main() -> None:
    """Run the MCP server."""
    config = get_config()
    config.ensure_directories()

    db = Database(config.database_path)
    db.initialize()

    vector_store = VectorStore(config.data_dir / "vector_db")

    mcp = create_mcp_server(db, vector_store)
    mcp.run()


if __name__ == "__main__":
    main()
