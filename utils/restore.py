# db/restore.py
from sqlalchemy.ext.asyncio import AsyncSession
from e2b import AsyncSandbox
from db.repositories import FileRepository
import logging

logger = logging.getLogger(__name__)


async def restore_project_files(
    session: AsyncSession,
    sandbox: AsyncSandbox,
    project_id: str
) -> dict[str, int]:
    """
    Restore all project files from database to sandbox.
    Returns dict mapping file paths to versions.
    """
    file_repo = FileRepository(session)
    latest_files = await file_repo.get_all_latest_files(project_id)
    
    restored = {}
    for file_version in latest_files:
        try:
            await sandbox.files.write(
                file_version.file_path,
                file_version.content
            )
            restored[file_version.file_path] = file_version.version
            logger.info(f"Restored {file_version.file_path} (v{file_version.version})")
        except Exception as e:
            logger.error(f"Failed to restore {file_version.file_path}: {e}")
    
    return restored
