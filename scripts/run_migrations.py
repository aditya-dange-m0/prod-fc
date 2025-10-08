"""
Helper script to run Alembic migrations with proper database configuration.
This ensures migrations use the DIRECT connection (port 5432) instead of pooled.

Usage:
    python scripts/run_migrations.py
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from db.config import get_db_settings


def main():
    """Set up environment and run Alembic migrations"""
    print("=" * 60)
    print("Running Database Migrations")
    print("=" * 60)
    
    settings = get_db_settings()
    
    # Get DIRECT connection URL for migrations (port 5432)
    direct_url = settings.get_connection_url(use_direct=True)
    
    # Convert asyncpg URL to sync for Alembic
    # Alembic uses psycopg2 by default (sync driver)
    sync_url = direct_url.replace("postgresql+asyncpg://", "postgresql://")
    
    print(f"✓ Using direct connection for migrations")
    print(f"✓ Database configured")
    print()
    
    # Set environment variable for Alembic (backup method)
    os.environ["ALEMBIC_DATABASE_URL"] = sync_url
    
    # Run Alembic upgrade
    print("Running: alembic upgrade head")
    print("-" * 60)
    exit_code = os.system("alembic upgrade head")
    
    if exit_code == 0:
        print("-" * 60)
        print("✅ Migrations completed successfully!")
    else:
        print("-" * 60)
        print(f"❌ Migration failed with exit code: {exit_code}")
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
