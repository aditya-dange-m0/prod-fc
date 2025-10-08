# db/config.py
import os
from pydantic_settings import BaseSettings
from typing import Optional


class DatabaseSettings(BaseSettings):
    """Database configuration settings for Supabase PostgreSQL"""
    
    # Supabase Connection Strings
    # Use DIRECT_DATABASE_URL for migrations (direct connection)
    # Use DATABASE_URL for application (pooled connection)
    DATABASE_URL: Optional[str] = None
    DIRECT_DATABASE_URL: Optional[str] = None
    
    # Individual connection parameters (fallback if URLs not provided)
    DB_HOST: Optional[str] = None
    DB_PORT: int = 6543  # Default to Supavisor pooler port
    DB_NAME: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    
    # Connection pool settings (for async operations)
    POOL_SIZE: int = 5  # Lower for serverless/pooled connections
    MAX_OVERFLOW: int = 10
    POOL_PRE_PING: bool = True
    
    # Logging
    ECHO_SQL: bool = False
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields from .env (like API keys, etc.)
    
    def get_connection_url(self, use_direct: bool = False) -> str:
        """
        Build connection URL for Supabase.
        
        Args:
            use_direct: If True, use direct connection (for migrations).
                       If False, use pooled connection (for application).
        
        Returns:
            Properly formatted asyncpg connection URL
        """
        # If explicit URLs provided, use them
        if use_direct and self.DIRECT_DATABASE_URL:
            url = self.DIRECT_DATABASE_URL
        elif not use_direct and self.DATABASE_URL:
            url = self.DATABASE_URL
        elif self.DB_HOST and self.DB_NAME and self.DB_USER and self.DB_PASSWORD:
            # Build from individual parameters
            # Use port 5432 for direct, 6543 for pooled
            port = 5432 if use_direct else self.DB_PORT
            url = (
                f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{port}/{self.DB_NAME}"
            )
        else:
            raise ValueError("Database connection parameters not configured")
        
        # Ensure URL uses asyncpg driver
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        return url


def get_db_settings() -> DatabaseSettings:
    """Get database settings from environment"""
    return DatabaseSettings()
