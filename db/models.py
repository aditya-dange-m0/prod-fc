# db/models.py
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Integer, Text, DateTime, Enum, ForeignKey, Index, JSON
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid
import enum


class Base(AsyncAttrs, DeclarativeBase):
    """Base model for all tables"""
    pass


def generate_uuid():
    return str(uuid.uuid4())


# =============================================================================
# ENUMS
# =============================================================================

class SandboxState(str, enum.Enum):
    RUNNING = "running"
    PAUSED = "paused"
    KILLED = "killed"
    NONE = "none"


class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"


# =============================================================================
# USER MODEL
# =============================================================================

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    projects: Mapped[list["Project"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# =============================================================================
# PROJECT MODEL
# =============================================================================

class Project(Base):
    __tablename__ = "projects"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # E2B Sandbox tracking
    active_sandbox_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sandbox_state: Mapped[SandboxState] = mapped_column(Enum(SandboxState), default=SandboxState.NONE)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_accessed: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="projects")
    sessions: Mapped[list["Session"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    file_versions: Mapped[list["FileVersion"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    snapshots: Mapped[list["ProjectSnapshot"]] = relationship(back_populates="project", cascade="all, delete-orphan")


# =============================================================================
# SESSION MODEL
# =============================================================================

class Session(Base):
    __tablename__ = "sessions"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    
    # Agno agent session tracking
    agno_session_id: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)
    
    # Session lifecycle
    status: Mapped[SessionStatus] = mapped_column(Enum(SessionStatus), default=SessionStatus.ACTIVE)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_active: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    project: Mapped["Project"] = relationship(back_populates="sessions")


# =============================================================================
# FILE VERSION MODEL
# =============================================================================

class FileVersion(Base):
    __tablename__ = "file_versions"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    
    # File metadata
    file_path: Mapped[str] = mapped_column(String(500), index=True)
    content: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    
    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)
    diff_from_previous: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Tracking
    created_by_tool: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    
    # Relationships
    project: Mapped["Project"] = relationship(back_populates="file_versions")
    
    __table_args__ = (
        Index("ix_file_versions_project_path_version", "project_id", "file_path", "version"),
    )


# =============================================================================
# PROJECT SNAPSHOT MODEL
# =============================================================================

class ProjectSnapshot(Base):
    __tablename__ = "project_snapshots"
    
    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    
    # Snapshot data
    snapshot_data: Mapped[dict] = mapped_column(JSON)
    sandbox_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    snapshot_type: Mapped[str] = mapped_column(String(50), default="manual")
    
    # Relationships
    project: Mapped["Project"] = relationship(back_populates="snapshots")


# =============================================================================
# EXPORTS - Ensure all models are registered for Alembic autogenerate
# =============================================================================

__all__ = [
    "Base",
    "User",
    "Project",
    "Session",
    "FileVersion",
    "ProjectSnapshot",
    "SandboxState",
    "SessionStatus",
]

