# db/repositories.py
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import difflib

from .models import User, Project, Session, FileVersion, ProjectSnapshot, SandboxState, SessionStatus


class UserRepository:
    """Repository for user operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_or_create_user(
        self,
        user_id: str,
        email: str,
        username: str
    ) -> User:
        """Get existing user or create new one"""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                id=user_id,
                email=email,
                username=username
            )
            self.session.add(user)
            await self.session.flush()
        
        return user


class FileRepository:
    """Repository for file operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save_file_version(
        self,
        project_id: str,
        file_path: str,
        content: str,
        created_by_tool: str
    ) -> FileVersion:
        """Save a new file version with automatic versioning"""
        
        # Get the latest version
        stmt = select(func.max(FileVersion.version)).where(
            FileVersion.project_id == project_id,
            FileVersion.file_path == file_path
        )
        result = await self.session.execute(stmt)
        latest_version = result.scalar() or 0
        
        # Get previous content for diff
        diff_text = None
        if latest_version > 0:
            prev_version = await self.get_file_version(project_id, file_path, latest_version)
            if prev_version:
                diff = difflib.unified_diff(
                    prev_version.content.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=f"{file_path} (v{latest_version})",
                    tofile=f"{file_path} (v{latest_version + 1})"
                )
                diff_text = ''.join(diff)
        
        # Create new version
        new_version = FileVersion(
            project_id=project_id,
            file_path=file_path,
            content=content,
            size_bytes=len(content.encode('utf-8')),
            version=latest_version + 1,
            diff_from_previous=diff_text,
            created_by_tool=created_by_tool
        )
        
        self.session.add(new_version)
        await self.session.flush()
        return new_version
    
    async def get_latest_file_version(
        self,
        project_id: str,
        file_path: str
    ) -> Optional[FileVersion]:
        """Get the latest version of a specific file"""
        stmt = select(FileVersion).where(
            FileVersion.project_id == project_id,
            FileVersion.file_path == file_path
        ).order_by(desc(FileVersion.version)).limit(1)
        
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_file_version(
        self,
        project_id: str,
        file_path: str,
        version: int
    ) -> Optional[FileVersion]:
        """Get a specific version of a file"""
        stmt = select(FileVersion).where(
            FileVersion.project_id == project_id,
            FileVersion.file_path == file_path,
            FileVersion.version == version
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all_latest_files(self, project_id: str) -> List[FileVersion]:
        """Get latest version of all files in a project"""
        subq = select(
            FileVersion.file_path,
            func.max(FileVersion.version).label("max_version")
        ).where(
            FileVersion.project_id == project_id
        ).group_by(FileVersion.file_path).subquery()
        
        stmt = select(FileVersion).join(
            subq,
            (FileVersion.file_path == subq.c.file_path) &
            (FileVersion.version == subq.c.max_version)
        ).where(FileVersion.project_id == project_id)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ProjectRepository:
    """Repository for project operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_or_create_project(
        self,
        user_id: str,
        project_id: str,
        project_name: str = "Default Project"
    ) -> Project:
        """Get existing project or create new one"""
        stmt = select(Project).where(Project.id == project_id)
        result = await self.session.execute(stmt)
        project = result.scalar_one_or_none()
        
        if not project:
            project = Project(
                id=project_id,
                user_id=user_id,
                name=project_name
            )
            self.session.add(project)
            await self.session.flush()
        
        return project
    
    async def update_sandbox_state(
        self,
        project_id: str,
        sandbox_id: Optional[str],
        state: SandboxState
    ):
        """Update project's sandbox information"""
        stmt = select(Project).where(Project.id == project_id)
        result = await self.session.execute(stmt)
        project = result.scalar_one_or_none()
        
        if project:
            project.active_sandbox_id = sandbox_id
            project.sandbox_state = state
            await self.session.flush()
