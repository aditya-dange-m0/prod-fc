# db/integration.py
"""
Database integration utilities for FileTools and agent operations.

This module provides wrapper functions to automatically save file operations
to the database while performing E2B sandbox operations.
"""

import logging
from typing import Optional
from datetime import datetime

from .session import get_db_session
from .repositories import FileRepository, ProjectRepository
from .models import User, SessionStatus


logger = logging.getLogger(__name__)


class DatabaseFileTracker:
    """
    Tracks file operations in database automatically.
    
    Use this wrapper in FileTools to save all write operations to database.
    """
    
    def __init__(self, user_id: str, project_id: str):
        self.user_id = user_id
        self.project_id = project_id
        self._initialized = False
    
    async def ensure_project_exists(self):
        """Ensure user and project exist in database"""
        if self._initialized:
            return
        
        try:
            async with get_db_session() as session:
                proj_repo = ProjectRepository(session)
                
                # Check if user exists, create if not
                from sqlalchemy import select
                from .models import User
                
                stmt = select(User).where(User.id == self.user_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if not user:
                    # Create user with defaults
                    user = User(
                        id=self.user_id,
                        email=f"{self.user_id}@system.local",
                        username=self.user_id
                    )
                    session.add(user)
                    await session.flush()
                    logger.info(f"Created user: {self.user_id}")
                
                # Create or get project
                await proj_repo.get_or_create_project(
                    user_id=self.user_id,
                    project_id=self.project_id,
                    project_name=f"Project {self.project_id}"
                )
                
                logger.info(f"Project ensured: {self.user_id}/{self.project_id}")
            
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to ensure project exists: {e}")
            # Don't fail the operation if DB tracking fails
    
    async def track_file_write(
        self,
        file_path: str,
        content: str,
        tool_name: str = "write_file"
    ) -> bool:
        """
        Track a file write operation in database.
        
        Args:
            file_path: Path of the file written
            content: Content of the file
            tool_name: Name of the tool that performed the operation
        
        Returns:
            True if tracking succeeded, False otherwise
        """
        try:
            await self.ensure_project_exists()
            
            async with get_db_session() as session:
                file_repo = FileRepository(session)
                
                await file_repo.save_file_version(
                    project_id=self.project_id,
                    file_path=file_path,
                    content=content,
                    created_by_tool=tool_name
                )
                
                logger.debug(f"Tracked file: {file_path} (project: {self.project_id})")
                return True
                
        except Exception as e:
            logger.error(f"Failed to track file write: {e}")
            return False
    
    async def update_sandbox_state(self, sandbox_id: Optional[str], state: str):
        """Update project's sandbox state in database"""
        try:
            await self.ensure_project_exists()
            
            async with get_db_session() as session:
                proj_repo = ProjectRepository(session)
                
                from .models import SandboxState
                sandbox_state = SandboxState(state) if state else SandboxState.NONE
                
                await proj_repo.update_sandbox_state(
                    project_id=self.project_id,
                    sandbox_id=sandbox_id,
                    state=sandbox_state
                )
                
                logger.debug(f"Updated sandbox state: {state}")
                
        except Exception as e:
            logger.error(f"Failed to update sandbox state: {e}")


async def get_or_create_session(
    project_id: str,
    agno_session_id: Optional[str] = None
) -> Optional[str]:
    """
    Get or create a session in database and link with Agno session.
    
    Args:
        project_id: Project ID
        agno_session_id: Agno agent session ID (optional)
    
    Returns:
        Database session ID or None if failed
    """
    try:
        async with get_db_session() as db_session:
            from sqlalchemy import select
            from .models import Session
            
            # Try to find existing active session for this project
            if agno_session_id:
                stmt = select(Session).where(
                    Session.agno_session_id == agno_session_id
                )
                result = await db_session.execute(stmt)
                session = result.scalar_one_or_none()
                
                if session:
                    # Update last active time
                    session.last_active = datetime.now()
                    await db_session.flush()
                    return session.id
            
            # Create new session
            new_session = Session(
                project_id=project_id,
                agno_session_id=agno_session_id,
                status=SessionStatus.ACTIVE
            )
            db_session.add(new_session)
            await db_session.flush()
            
            logger.info(f"Created session: {new_session.id} (Agno: {agno_session_id})")
            return new_session.id
            
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        return None


async def end_session(agno_session_id: str):
    """Mark a session as ended"""
    try:
        async with get_db_session() as db_session:
            from sqlalchemy import select
            from .models import Session
            
            stmt = select(Session).where(
                Session.agno_session_id == agno_session_id
            )
            result = await db_session.execute(stmt)
            session = result.scalar_one_or_none()
            
            if session:
                session.status = SessionStatus.ENDED
                session.ended_at = datetime.now()
                await db_session.flush()
                
                logger.info(f"Ended session: {session.id}")
                
    except Exception as e:
        logger.error(f"Failed to end session: {e}")
