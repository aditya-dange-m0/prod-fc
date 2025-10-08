"""
FileTools v2 - Enhanced E2B Sandbox File Operations
==================================================

Comprehensive file system operations for E2B sandbox environments, combining
best practices from Google's Gemini code and production E2B implementations.

Features:
- Type-safe operations with proper annotations
- Clear error messages for LLM understanding
- BOM detection and encoding handling
- File type detection and validation
- Agno agent compatible tool interfaces
- Performance optimized operations
"""

import asyncio
import mimetypes
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Literal, overload
from dataclasses import dataclass
from enum import Enum
import logging

from e2b import AsyncSandbox
from agno.tools import tool, Toolkit

from db.session import get_db_session
from db.repositories import FileRepository, ProjectRepository

from sandbox_manager import get_user_sandbox

# =============================================================================
# TYPE DEFINITIONS AND ENUMS
# =============================================================================


class FileType(Enum):
    """Supported file types for code operations"""

    TEXT = "text"


class ErrorType(Enum):
    """Error types for structured error handling"""

    FILE_NOT_FOUND = "file_not_found"
    PERMISSION_DENIED = "permission_denied"
    PATH_TRAVERSAL = "path_traversal"
    FILE_TOO_LARGE = "file_too_large"
    INVALID_PATH = "invalid_path"
    TARGET_IS_DIRECTORY = "target_is_directory"
    READ_FAILURE = "read_failure"
    WRITE_FAILURE = "write_failure"
    OPERATION_FAILED = "operation_failed"


@dataclass
class FileInfo:
    """Information about a file or directory"""

    name: str
    path: str
    type: Literal["file", "directory"]
    size: int
    modified: Optional[str] = None
    permissions: Optional[str] = None
    mime_type: Optional[str] = None


@dataclass
class FileOperationResult:
    """Result of a file operation"""

    success: bool
    path: str
    operation: str
    message: str
    size_bytes: int = 0
    error_type: Optional[ErrorType] = None
    error_details: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Create a structured logger for file operations"""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False

    return logger


def validate_sandbox_path(path: str) -> str:
    """
    Validate and normalize paths for E2B sandbox operations.

    Args:
        path: Path to validate

    Returns:
        Normalized path safe for sandbox operations

    Raises:
        ValueError: If path is invalid or contains security risks
    """
    if not path or not isinstance(path, str):
        raise ValueError("Path must be a non-empty string")

    path = path.strip()
    if not path:
        raise ValueError("Path cannot be empty")

    # Prevent directory traversal attacks
    if ".." in path:
        raise ValueError("Path traversal '..' not allowed for security")

    # Use posixpath for Linux sandbox compatibility
    import posixpath

    normalized = posixpath.normpath(path)

    # Double-check after normalization
    if ".." in normalized:
        raise ValueError("Path traversal detected after normalization")

    return normalized


def get_mime_type(file_path: str) -> Optional[str]:
    """
    Get MIME type for a file path.

    Args:
        file_path: Path to the file

    Returns:
        MIME type string or None if not detected
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type if isinstance(mime_type, str) else None


# =============================================================================
# MAIN FILE TOOLS CLASS
# =============================================================================


class FileTools(Toolkit):
    def __init__(
        self,
        user_id: str = "default_adi_001",
        project_id: str = "default_base_001",
        max_file_size: int = 50 * 1024 * 1024,  # 50MB default
        default_encoding: str = "utf-8",
        enable_db_tracking: bool = True,
        **kwargs,
    ):
        """
        Initialize FileToolkit with E2B sandbox.

        Args:
            user_id: User identifier for sandbox management
            project_id: Project identifier for sandbox management
            max_file_size: Maximum file size for operations in bytes
            default_encoding: Default text encoding
            enable_db_tracking: Enable database tracking of file operations
            **kwargs: Additional arguments passed to Toolkit
        """
        # Store sandbox and configuration
        self.user_id = user_id
        self.project_id = project_id
        self.max_file_size = max_file_size
        self.default_encoding = default_encoding
        self.enable_db_tracking = enable_db_tracking
        self.logger = setup_logger(f"{__name__}.FileToolkit")

        # Initialize the Toolkit with all tool methods
        # tools=[
        #     self.read_file,
        #     self.write_file,
        #     self.file_exists,
        #     self.get_file_info,
        #     self.list_directory,
        #     self.create_directory,
        #     self.delete_path,
        #     self.delete_file,  # backward compatibility
        #     self.delete_directory,  # backward compatibility
        # ],
        super().__init__(name="file_toolkit")
        self.register(self.read_file)
        self.register(self.write_file)
        self.register(self.file_exists)
        self.register(self.get_file_info)
        self.register(self.list_directory)
        self.register(self.create_directory)
        self.register(self.delete_file)
        self.register(self.delete_directory)

        self.logger.info(f"FileToolkit initialized - max_size: {max_file_size}MB")

    # =========================================================================
    # CORE FILE OPERATIONS
    # =========================================================================
    async def read_file(
        self,
        path: str,  # The absolute path to the file to read
        offset: Optional[
            int
        ] = None,  # The line number to start reading from (optional)
        limit: Optional[int] = None,  # The number of lines to read (optional)
    ) -> str:
        """
        Read file content from E2B sandbox as text.

        Args:
            path: File path in sandbox
            offset: Starting line number (0-based)
            limit: Maximum lines to read

        Returns:
            File content as string

        Raises:
            ValueError: If path is invalid
            FileNotFoundError: If file doesn't exist
            PermissionError: If access is denied
            OSError: If other I/O errors occur
        """
        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            path = validate_sandbox_path(path)
            self.logger.debug(f"Reading text file: {path}")

            # Read as text from E2B
            content = await sandbox.files.read(path, format="text")

            # Handle line-based reading for text files
            if offset is not None or limit is not None:
                lines = content.splitlines()
                start = offset or 0
                end = (start + limit) if limit else len(lines)

                if start >= len(lines):
                    return ""

                selected_lines = lines[start : min(end, len(lines))]
                content = "\n".join(selected_lines)

            self.logger.info(
                f"Successfully read text file: {path} ({len(content)} chars)"
            )
            return content

        except Exception as e:
            error_msg = str(e).lower()

            if "not found" in error_msg or "no such file" in error_msg:
                raise FileNotFoundError(
                    f"File '{path}' does not exist in the sandbox. "
                    f"Please verify the path is correct or create the file first."
                ) from e

            elif "permission" in error_msg or "access" in error_msg:
                raise PermissionError(
                    f"Permission denied accessing file '{path}'. "
                    f"Check file permissions or try a different location."
                ) from e

            else:
                self.logger.error(f"Failed to read file {path}: {e}")
                raise OSError(f"Unable to read file '{path}': {e}") from e

    async def write_file(
        self,
        path: str,
        content: str,
        overwrite: bool = True,
        timeout: Optional[float] = None,
    ) -> FileOperationResult:
        """
        Write content to file using E2B's native write method with automatic directory creation.

        Args:
            path: Target file path (must be valid sandbox path)
            content: Text content to write (only strings supported for code files)
            overwrite: Whether to overwrite existing files
            user: User to run the operation as
            timeout: Request timeout in seconds

        Returns:
            FileOperationResult with operation details

        Raises:
            ValueError: If path/content is invalid
            FileExistsError: If file exists and overwrite=False
            PermissionError: If access is denied
            OSError: If write operation fails
        """
        try:
            # Validate inputs
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            path = validate_sandbox_path(path)
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            if not isinstance(content, str):
                raise ValueError(
                    f"Content must be a string for text files. Got {type(content).__name__}. "
                    f"Convert to string before writing."
                )

            # Validate content size
            content_size = len(content.encode(self.default_encoding))
            if content_size > self.max_file_size:
                raise ValueError(
                    f"File content too large: {content_size} bytes exceeds limit of {self.max_file_size} bytes. "
                    f"Consider splitting the content or increasing the limit."
                )

            self.logger.debug(
                f"Writing file: {path} ({len(content)} chars, {content_size} bytes)"
            )

            # Check if file exists for overwrite validation
            file_exists = await self.file_exists(path)

            if file_exists and not overwrite:
                raise FileExistsError(
                    f"File '{path}' already exists. Set overwrite=True to replace it, "
                    f"or choose a different file path."
                )

            # Use E2B's native write method (automatically creates directories)
            write_info = await sandbox.files.write(
                path=path, data=content, request_timeout=timeout
            )
            
            await self._persist_file_to_db(path, content, "write_file")

            # Calculate metrics
            line_count = len(content.splitlines())
            content_size = len(content.encode("utf-8"))  # Calculate size from content
            operation_type = "created" if not file_exists else "updated"

            # Create result using WriteInfo from E2B
            result = FileOperationResult(
                success=True,
                path=write_info.path,
                operation=f"write_file_{operation_type.rstrip('d')}",
                message=f"Successfully {operation_type} file '{Path(path).name}' "
                f"({content_size} bytes, {line_count} lines)",
                size_bytes=content_size,
            )

            self.logger.info(
                f"Successfully wrote file: {path} "
                f"({operation_type}, {content_size} bytes, {line_count} lines)"
            )
            return result

        except (ValueError, FileExistsError, PermissionError, OSError):
            # Re-raise known exceptions as-is
            raise
        except Exception as e:
            # Handle unexpected errors with clear messages for LLM
            error_msg = str(e)

            if "permission" in error_msg.lower():
                raise PermissionError(
                    f"Access denied when writing to '{path}'. Check file permissions "
                    f"or try a different location. Error: {e}"
                ) from e
            else:
                self.logger.error(f"Unexpected error writing file {path}: {e}")
                raise OSError(
                    f"Failed to write file '{path}'. This may be due to sandbox limitations, "
                    f"network issues, or file system errors. Error: {e}"
                ) from e

    async def file_exists(self, path: str) -> bool:
        """
        Check if a file or directory exists in the sandbox using E2B native method.

        Args:
            path: Path to check

        Returns:
            True if file/directory exists, False otherwise
        """

        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            path = validate_sandbox_path(path)
            # Use E2B's native exists() method - much more efficient and reliable
            return await sandbox.files.exists(path)
        except Exception as e:
            self.logger.debug(f"Error checking file existence for {path}: {e}")
            return False

    async def get_file_info(self, path: str) -> FileInfo:
        """
        Get detailed information about a file or directory using E2B native method.

        Args:
            path: Path to examine

        Returns:
            FileInfo object with file details

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            path = validate_sandbox_path(path)

            # Use E2B's native get_info() method - much more efficient and reliable
            entry_info = await sandbox.files.get_info(path)

            # Convert E2B FileType to our format
            file_type = "directory" if entry_info.type.value == "dir" else "file"

            # Get MIME type for files
            mime_type = None
            if file_type == "file":
                mime_type = get_mime_type(path)

            return FileInfo(
                name=entry_info.name,
                path=entry_info.path,
                type=file_type,
                size=entry_info.size,
                modified=(
                    entry_info.modified_time.isoformat()
                    if entry_info.modified_time
                    else None
                ),
                permissions=entry_info.permissions,
                mime_type=mime_type,
            )

        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "no such file" in error_msg:
                raise FileNotFoundError(f"Path '{path}' not found in sandbox") from e
            else:
                raise OSError(f"Failed to get file info for '{path}': {e}") from e

    async def list_directory(
        self, path: str = ".", depth: Optional[int] = 1, include_hidden: bool = False
    ) -> List[FileInfo]:
        """
        List directory contents using E2B native list() method.

        Args:
            path: Directory path to list
            depth: Depth of recursion (1 = immediate children, None = unlimited)
            include_hidden: Whether to include hidden files (starting with .)

        Returns:
            List of FileInfo objects for each entry

        Raises:
            FileNotFoundError: If directory doesn't exist
            NotADirectoryError: If path is not a directory
            OSError: If listing fails
        """
        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            path = validate_sandbox_path(path)
            self.logger.debug(
                f"Listing directory: {path} (depth={depth}, hidden={include_hidden})"
            )

            # Use E2B's native list() method - much more efficient
            entries_info = await sandbox.files.list(path, depth=depth)

            file_entries = []
            for entry_info in entries_info:
                # Skip hidden files if not requested
                if not include_hidden and entry_info.name.startswith("."):
                    continue

                # Convert E2B EntryInfo to our FileInfo format
                file_type = "directory" if entry_info.type.value == "dir" else "file"

                # Get MIME type for files only
                mime_type = None
                if file_type == "file":
                    mime_type = get_mime_type(entry_info.path)

                file_info = FileInfo(
                    name=entry_info.name,
                    path=entry_info.path,
                    type=file_type,
                    size=entry_info.size,
                    modified=(
                        entry_info.modified_time.isoformat()
                        if entry_info.modified_time
                        else None
                    ),
                    permissions=entry_info.permissions,
                    mime_type=mime_type,
                )
                file_entries.append(file_info)

            self.logger.info(f"Listed {len(file_entries)} entries in directory: {path}")
            return file_entries

        except Exception as e:
            error_msg = str(e).lower()
            if "not found" in error_msg or "no such file" in error_msg:
                raise FileNotFoundError(
                    f"Directory '{path}' not found in sandbox"
                ) from e
            elif "not a directory" in error_msg:
                raise NotADirectoryError(f"'{path}' is not a directory") from e
            else:
                self.logger.error(f"Failed to list directory '{path}': {e}")
                raise OSError(f"Failed to list directory '{path}': {e}") from e

    async def create_directory(
        self, path: str, recursive: bool = True
    ) -> FileOperationResult:
        """
        Create a directory in the sandbox using E2B's native make_dir method.

        Args:
            path: Directory path to create
            recursive: Whether to create parent directories (always True with E2B make_dir)

        Returns:
            FileOperationResult with operation details

        Raises:
            ValueError: If path is invalid
            OSError: If directory creation fails
        """
        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            path = validate_sandbox_path(path)
            self.logger.debug(f"Creating directory: {path}")

            # Use E2B's native make_dir method (automatically recursive)
            created = await sandbox.files.make_dir(path)

            if created:
                message = f"Successfully created directory '{path}'"
            else:
                message = f"Directory '{path}' already exists"

            self.logger.info(message)

            return FileOperationResult(
                success=True,
                path=path,
                operation="create_directory",
                message=message,
            )

        except (ValueError, OSError):
            raise
        except Exception as e:
            error_msg = f"Failed to create directory '{path}': {e}"
            self.logger.error(error_msg)
            raise OSError(error_msg) from e

    async def delete_path(self, path: str, force: bool = False) -> FileOperationResult:
        """
        Delete a file or directory from the sandbox using E2B's native remove method.

        Args:
            path: Path to file or directory to delete
            force: Whether to ignore if path doesn't exist

        Returns:
            FileOperationResult with operation details

        Raises:
            ValueError: If path is invalid
            FileNotFoundError: If path doesn't exist and force=False
            OSError: If deletion fails
        """
        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            path = validate_sandbox_path(path)
            self.logger.debug(f"Deleting path: {path} (force={force})")

            # Check if path exists first (unless force=True)
            if not force and not await self.file_exists(path):
                raise FileNotFoundError(
                    f"Path '{path}' does not exist. Use force=True to ignore missing files/directories."
                )

            # Determine what we're deleting for better logging
            try:
                info = await self.get_file_info(path)
                item_type = info.type
            except:
                item_type = "item"  # Unknown type

            # Use E2B's native remove() method - handles files and directories automatically
            await sandbox.files.remove(path)

            return FileOperationResult(
                success=True,
                path=path,
                operation="delete_path",
                message=f"Successfully deleted {item_type} '{path}'",
            )

        except (ValueError, FileNotFoundError):
            raise
        except Exception as e:
            error_msg = str(e).lower()

            if "not found" in error_msg and force:
                # If force=True and file doesn't exist, consider it success
                return FileOperationResult(
                    success=True,
                    path=path,
                    operation="delete_path",
                    message=f"Path '{path}' already deleted or doesn't exist",
                )
            elif "not empty" in error_msg:
                raise OSError(
                    f"Directory '{path}' is not empty. Empty the directory first or use a recursive deletion method."
                ) from e
            else:
                self.logger.error(f"Failed to delete path '{path}': {e}")
                raise OSError(f"Failed to delete '{path}': {e}") from e

    async def delete_file(self, path: str, force: bool = False) -> FileOperationResult:
        """Backward compatibility alias for delete_path - use delete_path instead"""
        return await self.delete_path(path, force)

    async def delete_directory(
        self, path: str, recursive: bool = False
    ) -> FileOperationResult:
        """Backward compatibility alias for delete_path - use delete_path instead"""
        if not recursive:
            self.logger.warning(
                "delete_directory with recursive=False may fail if directory is not empty. Use delete_path instead."
            )
        return await self.delete_path(path, force=False)

    async def _persist_file_to_db(self, path: str, content: str, tool_name: str):
        """
        Internal method to persist file changes to database.
        Called automatically after successful file operations.
        """
        if not self.enable_db_tracking:
            return
        
        try:
            async with get_db_session() as session:
                file_repo = FileRepository(session)
                project_repo = ProjectRepository(session)
                
                # Ensure user exists
                from sqlalchemy import select
                from db.models import User
                
                stmt = select(User).where(User.id == self.user_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                
                if not user:
                    user = User(
                        id=self.user_id,
                        email=f"{self.user_id}@system.local",
                        username=self.user_id
                    )
                    session.add(user)
                    await session.flush()
                
                # Ensure project exists
                await project_repo.get_or_create_project(
                    user_id=self.user_id,
                    project_id=self.project_id
                )
                
                # Save file version
                await file_repo.save_file_version(
                    project_id=self.project_id,
                    file_path=path,
                    content=content,
                    created_by_tool=tool_name
                )
                
                self.logger.debug(f"Persisted {path} to database")
        except Exception as e:
            self.logger.error(f"Failed to persist {path} to database: {e}")
            # Don't raise - file write already succeeded in sandbox

if __name__ == "__main__":
    print("FileTools v1 - Enhanced E2B Sandbox File Operations")
    print("Available classes: FileTools, FileInfo, FileOperationResult")
    print("Available functions: create_file_tools, create_agno_file_tools")
    print("Ready for production use with Agno agents!")
