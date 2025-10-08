# db/__init__.py
"""
Database package for multi-tenant file and session management.

This package provides:
- Models: User, Project, Session, FileVersion, ProjectSnapshot
- Repositories: FileRepository, ProjectRepository
- Session management: Database connection and session factory
- Configuration: Database settings
"""

from .models import (
    Base,
    User,
    Project,
    Session,
    FileVersion,
    ProjectSnapshot,
    SandboxState,
    SessionStatus,
)

from .session import (
    init_db,
    get_db_session,
    get_engine,
    get_session_factory,
    close_db,
)

from .repositories import (
    UserRepository,
    FileRepository,
    ProjectRepository,
)

from .config import (
    get_db_settings,
    DatabaseSettings,
)

__all__ = [
    # Models
    "Base",
    "User",
    "Project",
    "Session",
    "FileVersion",
    "ProjectSnapshot",
    "SandboxState",
    "SessionStatus",
    
    # Session management
    "init_db",
    "get_db_session",
    "get_engine",
    "get_session_factory",
    "close_db",
    
    # Repositories
    "UserRepository",
    "FileRepository",
    "ProjectRepository",
    
    # Configuration
    "get_db_settings",
    "DatabaseSettings",
]
