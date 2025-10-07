"""
CommandTools v2 - Enhanced E2B Sandbox Command Operations
==========================================================

Comprehensive command execution operations for E2B sandbox environments with
support for simple commands, long-running services, process management, and
streaming output.

Features:
- Simple command execution with timeout support
- Long-running service management (servers, React frontends, etc.)
- Process listing and killing
- Stdin streaming for interactive commands
- Output streaming with callbacks
- Background process management
- Type-safe operations with proper annotations
- Clear error messages for LLM understanding
- Agno agent compatible tool interfaces
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from agno.tools import Toolkit

from sandbox_manager import get_user_sandbox


# =============================================================================
# TYPE DEFINITIONS AND ENUMS
# =============================================================================


class ProcessStatus(Enum):
    """Process execution status"""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    KILLED = "killed"


class ServiceType(Enum):
    """Types of long-running services"""

    WEB_SERVER = "web_server"
    API_SERVER = "api_server"
    FRONTEND_DEV = "frontend_dev"  # React, Vue, Angular dev servers
    DATABASE = "database"
    BACKGROUND_TASK = "background_task"
    CUSTOM = "custom"


@dataclass
class ProcessInfo:
    """Information about a running process"""

    pid: int
    tag: str
    cmd: str
    args: List[str]
    envs: Dict[str, str]
    cwd: str

    def __str__(self) -> str:
        args_str = " ".join(self.args) if self.args else ""
        full_cmd = f"{self.cmd} {args_str}".strip()
        return f"PID {self.pid}: {full_cmd} (cwd: {self.cwd})"


@dataclass
class CommandResult:
    """Result of a command execution"""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    pid: Optional[int] = None
    status: ProcessStatus = ProcessStatus.COMPLETED
    error_message: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

        # Determine status based on exit code if not set
        if self.exit_code == 0:
            self.status = ProcessStatus.COMPLETED
        elif self.exit_code != 0:
            self.status = ProcessStatus.FAILED

    @property
    def success(self) -> bool:
        """Whether command executed successfully"""
        return self.exit_code == 0

    @property
    def failed(self) -> bool:
        """Whether command failed"""
        return not self.success

    def get_summary(self) -> str:
        """Get human-readable summary"""
        status_str = "✓" if self.success else "✗"
        cmd_preview = self.command[:50] + "..." if len(self.command) > 50 else self.command
        return (
            f"[{status_str}] {cmd_preview} | "
            f"Exit: {self.exit_code} | "
            f"Time: {self.execution_time:.2f}s"
        )


@dataclass
class ServiceInfo:
    """Information about a running service"""

    pid: int
    service_type: ServiceType
    command: str
    port: Optional[int] = None
    public_url: Optional[str] = None
    started_at: datetime = None
    description: Optional[str] = None

    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)

    def get_info(self) -> str:
        """Get formatted service information"""
        info = f"Service PID {self.pid} ({self.service_type.value})"
        if self.port:
            info += f" on port {self.port}"
        if self.public_url:
            info += f"\nPublic URL: {self.public_url}"
        if self.description:
            info += f"\nDescription: {self.description}"
        return info


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Create a structured logger for command operations"""
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


def validate_command(command: str) -> str:
    """
    Validate command for security and safety.

    Args:
        command: Command string to validate

    Returns:
        Validated command string

    Raises:
        ValueError: If command is invalid or dangerous
    """
    if not command or not isinstance(command, str):
        raise ValueError("Command must be a non-empty string")

    command = command.strip()
    if not command:
        raise ValueError("Command cannot be empty")

    # Security checks - prevent extremely dangerous operations
    dangerous_patterns = [
        "rm -rf /",
        "rm -rf /*",
        "format",
        "mkfs",
        "> /dev/sda",
    ]

    command_lower = command.lower()
    for pattern in dangerous_patterns:
        if pattern in command_lower:
            raise ValueError(
                f"Extremely dangerous command pattern detected: '{pattern}'. "
                f"This operation is blocked for safety."
            )

    return command


# =============================================================================
# MAIN COMMAND TOOLS CLASS
# =============================================================================


class CommandTools(Toolkit):
    def __init__(
        self,
        user_id: str = "default_adi_001",
        project_id: str = "default_base_001",
        default_timeout: int = 60,
        max_output_size: int = 1024 * 1024,  # 1MB default
        **kwargs,
    ):
        """
        Initialize CommandTools with E2B sandbox.

        Args:
            user_id: User identifier for sandbox management
            project_id: Project identifier for sandbox management
            default_timeout: Default command timeout in seconds
            max_output_size: Maximum output size in bytes
            **kwargs: Additional arguments passed to Toolkit
        """
        # Store configuration
        self.user_id = user_id
        self.project_id = project_id
        self.default_timeout = default_timeout
        self.max_output_size = max_output_size
        self.logger = setup_logger(f"{__name__}.CommandTools")

        # Track running services
        self.running_services: Dict[int, ServiceInfo] = {}
        
        # Track background command handles
        self.background_commands: Dict[int, Any] = {}

        # Initialize the Toolkit
        super().__init__(name="command_toolkit")

        # Register all tools
        self.register(self.run_command)
        self.register(self.run_service)
        self.register(self.list_processes)
        self.register(self.kill_process)
        # self.register(self.send_stdin)
        # self.register(self.get_service_url)
        # self.register(self.stop_service)
        # self.register(self.list_services)
        # self.register(self.connect_to_process)

        self.logger.info(
            f"CommandTools initialized - timeout: {default_timeout}s, "
            f"max_output: {max_output_size} bytes"
        )

    # =========================================================================
    # CORE COMMAND OPERATIONS
    # =========================================================================

    async def run_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Run a simple shell command and wait for it to complete.

        This is for short-running commands like `ls`, `echo`, `cat`, `npm install`, etc.
        For long-running services (servers, dev servers), use `run_service` instead.

        Args:
            command: Shell command to execute
            timeout: Timeout in seconds (default: 60s)
            cwd: Working directory to run the command in
            envs: Environment variables for the command

        Returns:
            Formatted string with command results (stdout, stderr, exit code)

        Raises:
            ValueError: If command is invalid or dangerous
            TimeoutError: If command exceeds timeout
            RuntimeError: If command execution fails
        """
        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            
            # Validate command
            validated_command = validate_command(command)
            timeout = timeout or self.default_timeout

            self.logger.info(
                f"Executing command: {validated_command[:100]}... "
                f"(timeout={timeout}s, cwd={cwd})"
            )

            start_time = datetime.now()

            # Execute command using E2B's run method (background=False by default)
            # This will wait for the command to complete
            result = await sandbox.commands.run(
                validated_command,
                envs=envs,
                cwd=cwd,
                timeout=timeout,
            )

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            # Create result object
            cmd_result = CommandResult(
                command=validated_command,
                exit_code=result.exit_code,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                execution_time=execution_time,
                error_message=result.error if hasattr(result, "error") else None,
            )

            # Log result
            self.logger.info(f"Command completed: {cmd_result.get_summary()}")

            # Format output for agent
            output = f"Command: {validated_command}\n"
            output += f"Exit Code: {result.exit_code}\n"
            output += f"Execution Time: {execution_time:.2f}s\n"
            output += f"Status: {'✓ Success' if cmd_result.success else '✗ Failed'}\n\n"

            if result.stdout:
                output += f"=== STDOUT ===\n{result.stdout}\n\n"

            if result.stderr:
                output += f"=== STDERR ===\n{result.stderr}\n\n"

            if cmd_result.error_message:
                output += f"=== ERROR ===\n{cmd_result.error_message}\n"

            return output

        except Exception as e:
            error_msg = str(e).lower()

            if "timeout" in error_msg or "timed out" in error_msg:
                self.logger.error(f"Command timed out: {e}")
                return json.dumps({
                    "status": "error",
                    "error_type": "timeout",
                    "message": f"Command timed out after {timeout} seconds. Consider increasing timeout or using run_service for long-running commands.",
                    "details": str(e)
                })
            else:
                self.logger.error(f"Command execution failed: {e}")
                return json.dumps({
                    "status": "error",
                    "message": f"Command execution failed: {str(e)}"
                })

    async def run_service(
        self,
        command: str,
        port: Optional[int] = None,
        service_type: str = "custom",
        description: Optional[str] = None,
        cwd: Optional[str] = None,
        envs: Optional[Dict[str, str]] = None,
        wait_for_port: bool = True,
    ) -> str:
        """
        Run a long-running service in the background (servers, React dev server, etc.).

        This starts a background process and optionally exposes it via a public URL.
        Use this for:
        - Web servers (Express, Flask, FastAPI)
        - Frontend dev servers (React, Vue, Angular - npm run dev/start)
        - API servers
        - Database servers
        - Any long-running background task

        Args:
            command: Command to start the service (e.g., "npm run dev", "python app.py")
            port: Port number the service will listen on (for URL generation)
            service_type: Type of service (web_server, frontend_dev, api_server, etc.)
            description: Human-readable description of the service
            cwd: Working directory to run the service in
            envs: Environment variables for the service
            wait_for_port: Wait a moment for service to start on port

        Returns:
            Service information including PID and public URL (if port specified)

        Raises:
            ValueError: If command is invalid
            RuntimeError: If service fails to start
        """
        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            
            # Validate command
            validated_command = validate_command(command)

            # Parse service type
            try:
                svc_type = ServiceType[service_type.upper()]
            except KeyError:
                svc_type = ServiceType.CUSTOM

            self.logger.info(
                f"Starting service: {validated_command[:100]}... "
                f"(type={svc_type.value}, port={port}, cwd={cwd})"
            )

            # Execute command in background using E2B's run method
            process = await sandbox.commands.run(
                validated_command,
                envs=envs,
                cwd=cwd,
                background=True,  # This is the key - run in background
            )

            # Get PID from the background process handle
            pid = process.pid
            
            # Track the command handle for later use
            self.background_commands[pid] = process

            # Wait a moment for service to start
            if wait_for_port and port:
                await asyncio.sleep(2)

            # Get public URL if port is specified
            public_url = None
            if port:
                try:
                    host = await sandbox.get_host(port)
                    public_url = f"http://{host}"
                    self.logger.info(f"Service available at: {public_url}")
                except Exception as e:
                    self.logger.warning(f"Could not get public URL for port {port}: {e}")

            # Create service info
            service_info = ServiceInfo(
                pid=pid,
                service_type=svc_type,
                command=validated_command,
                port=port,
                public_url=public_url,
                description=description or f"{svc_type.value} on port {port}",
            )

            # Track the service
            self.running_services[pid] = service_info

            # Format output for agent
            output = f"✓ Service started successfully!\n\n"
            output += f"PID: {pid}\n"
            output += f"Type: {svc_type.value}\n"
            output += f"Command: {validated_command}\n"

            if port:
                output += f"Port: {port}\n"

            if public_url:
                output += f"\n🌐 Public URL: {public_url}\n"
                output += f"\nYou can access the service at: {public_url}\n"

            if description:
                output += f"\nDescription: {description}\n"

            output += f"\nUse kill_process({pid}) to stop this service.\n"

            self.logger.info(f"Service started - PID: {pid}, Type: {svc_type.value}")

            return output

        except Exception as e:
            self.logger.error(f"Failed to start service: {e}")
            return json.dumps({
                "status": "error",
                "message": f"Failed to start service: {str(e)}"
            })

    # =========================================================================
    # PROCESS MANAGEMENT
    # =========================================================================

    async def list_processes(self) -> str:
        """
        List all running processes in the sandbox.

        Returns:
            Formatted list of all running processes with details

        Raises:
            RuntimeError: If listing processes fails
        """
        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            
            # Use E2B's list method to get all running processes
            processes = await sandbox.commands.list()

            if not processes:
                return "No processes currently running in the sandbox."

            # Format output
            output = f"=== Running Processes ({len(processes)}) ===\n\n"

            for proc in processes:
                # Convert to our ProcessInfo type
                proc_info = ProcessInfo(
                    pid=proc.pid,
                    tag=proc.tag or "",
                    cmd=proc.cmd,
                    args=list(proc.args) if proc.args else [],
                    envs=dict(proc.envs) if proc.envs else {},
                    cwd=proc.cwd or "/",
                )

                output += f"PID: {proc_info.pid}\n"
                output += f"Command: {proc_info.cmd}\n"

                if proc_info.args:
                    output += f"Args: {' '.join(proc_info.args)}\n"

                output += f"CWD: {proc_info.cwd}\n"

                if proc_info.tag:
                    output += f"Tag: {proc_info.tag}\n"

                # Check if this is a tracked service
                if proc_info.pid in self.running_services:
                    service = self.running_services[proc_info.pid]
                    output += f"Service Type: {service.service_type.value}\n"
                    if service.port:
                        output += f"Port: {service.port}\n"
                    if service.public_url:
                        output += f"URL: {service.public_url}\n"

                output += "\n" + "-" * 60 + "\n\n"

            self.logger.info(f"Listed {len(processes)} running processes")
            return output

        except Exception as e:
            self.logger.error(f"Failed to list processes: {e}")
            return json.dumps({
                "status": "error",
                "message": f"Failed to list processes: {str(e)}"
            })

    async def kill_process(self, pid: int) -> str:
        """
        Kill a running process by its PID.

        This sends a SIGKILL signal to the process, immediately terminating it.
        Use this to stop services started with run_service or any other running process.

        Args:
            pid: Process ID to kill

        Returns:
            Status message indicating whether process was killed

        Raises:
            ValueError: If PID is invalid
            RuntimeError: If kill operation fails
        """
        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            
            if not isinstance(pid, int) or pid <= 0:
                return json.dumps({
                    "status": "error",
                    "message": f"Invalid PID: {pid}. PID must be a positive integer."
                })

            self.logger.info(f"Killing process: {pid}")

            # Use E2B's kill method
            killed = await sandbox.commands.kill(pid)

            # Remove from tracked services if it was a service
            service_info = self.running_services.pop(pid, None)
            
            # Remove from background commands
            cmd_handle = self.background_commands.pop(pid, None)

            if killed:
                output = f"✓ Successfully killed process {pid}\n"

                if service_info:
                    output += f"\nService Details:\n"
                    output += f"Type: {service_info.service_type.value}\n"
                    output += f"Command: {service_info.command}\n"
                    if service_info.port:
                        output += f"Port: {service_info.port}\n"

                self.logger.info(f"Successfully killed process {pid}")
            else:
                output = f"Process {pid} not found or already terminated.\n"
                self.logger.warning(f"Process {pid} not found")

            return output

        except Exception as e:
            self.logger.error(f"Failed to kill process {pid}: {e}")
            return json.dumps({
                "status": "error",
                "message": f"Failed to kill process {pid}: {str(e)}"
            })

    async def send_stdin(self, pid: int, data: str) -> str:
        """
        Send data to a process's stdin stream.

        Use this for interactive commands that accept stdin input.

        Args:
            pid: Process ID to send data to
            data: String data to send to stdin

        Returns:
            Status message

        Raises:
            ValueError: If PID or data is invalid
            RuntimeError: If sending stdin fails
        """
        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            
            if not isinstance(pid, int) or pid <= 0:
                return json.dumps({
                    "status": "error",
                    "message": f"Invalid PID: {pid}. PID must be a positive integer."
                })

            if not isinstance(data, str):
                return json.dumps({
                    "status": "error",
                    "message": "Data must be a string"
                })

            self.logger.info(f"Sending stdin to process {pid}: {len(data)} chars")

            # Use E2B's send_stdin method
            await sandbox.commands.send_stdin(pid, data)

            output = f"✓ Successfully sent {len(data)} characters to process {pid}\n"
            self.logger.info(f"Sent stdin to process {pid}")

            return output

        except Exception as e:
            self.logger.error(f"Failed to send stdin to process {pid}: {e}")
            return json.dumps({
                "status": "error",
                "message": f"Failed to send stdin to process {pid}: {str(e)}"
            })

    # =========================================================================
    # SERVICE MANAGEMENT
    # =========================================================================

    async def get_service_url(self, port: int) -> str:
        """
        Get the public URL for a service running on a specific port.

        Args:
            port: Port number the service is listening on

        Returns:
            Public URL for the service

        Raises:
            ValueError: If port is invalid
            RuntimeError: If URL generation fails
        """
        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            
            if not isinstance(port, int) or port <= 0 or port > 65535:
                return json.dumps({
                    "status": "error",
                    "message": f"Invalid port: {port}. Port must be between 1 and 65535."
                })

            self.logger.info(f"Getting public URL for port {port}")

            # Use E2B's get_host method (async for AsyncSandbox)
            host = await sandbox.get_host(port)
            url = f"http://{host}"

            output = f"Public URL for port {port}:\n{url}\n"
            self.logger.info(f"Generated URL for port {port}: {url}")

            return output

        except Exception as e:
            self.logger.error(f"Failed to get URL for port {port}: {e}")
            return json.dumps({
                "status": "error",
                "message": f"Failed to get URL for port {port}. Ensure a service is running on this port. Error: {str(e)}"
            })

    async def stop_service(self, pid: int) -> str:
        """
        Stop a running service by its PID (alias for kill_process).

        Args:
            pid: Process ID of the service to stop

        Returns:
            Status message

        Raises:
            ValueError: If PID is invalid
            RuntimeError: If stop operation fails
        """
        return await self.kill_process(pid)

    async def list_services(self) -> str:
        """
        List all tracked running services.

        Returns:
            Formatted list of all tracked services

        Raises:
            RuntimeError: If listing fails
        """
        try:
            if not self.running_services:
                return "No tracked services currently running."

            output = f"=== Tracked Services ({len(self.running_services)}) ===\n\n"

            for pid, service in self.running_services.items():
                output += f"PID: {pid}\n"
                output += f"Type: {service.service_type.value}\n"
                output += f"Command: {service.command}\n"

                if service.port:
                    output += f"Port: {service.port}\n"

                if service.public_url:
                    output += f"URL: {service.public_url}\n"

                if service.description:
                    output += f"Description: {service.description}\n"

                output += f"Started: {service.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                output += "\n" + "-" * 60 + "\n\n"

            return output

        except Exception as e:
            self.logger.error(f"Failed to list services: {e}")
            return json.dumps({
                "status": "error",
                "message": f"Failed to list services: {str(e)}"
            })

    async def connect_to_process(
        self,
        pid: int,
        timeout: Optional[int] = None,
    ) -> str:
        """
        Connect to an existing running process to receive its output.

        Useful for reconnecting to processes that were started in the background
        or to monitor already running processes.

        Args:
            pid: Process ID to connect to
            timeout: Connection timeout in seconds

        Returns:
            Connection status message

        Raises:
            Returns JSON error if connection fails
        """
        try:
            sandbox = await get_user_sandbox(self.user_id, self.project_id)
            
            if not isinstance(pid, int) or pid <= 0:
                return json.dumps({
                    "status": "error",
                    "message": f"Invalid PID: {pid}. PID must be a positive integer."
                })

            self.logger.info(f"Connecting to process {pid}")

            # Use E2B's connect method
            cmd_handle = await sandbox.commands.connect(
                pid=pid,
                timeout=timeout or self.default_timeout,
            )

            # Store the command handle
            self.background_commands[pid] = cmd_handle

            output = f"✓ Successfully connected to process {pid}\n"
            output += f"You can now interact with this process using send_stdin or kill_process.\n"

            self.logger.info(f"Connected to process {pid}")
            return output

        except Exception as e:
            self.logger.error(f"Failed to connect to process {pid}: {e}")
            return json.dumps({
                "status": "error",
                "message": f"Failed to connect to process {pid}: {str(e)}"
            })


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_command_tools(
    user_id: str = "default_adi_001",
    project_id: str = "default_base_001",
    config: Optional[Dict[str, Any]] = None,
) -> CommandTools:
    """
    Factory function to create CommandTools instance.

    Args:
        user_id: User identifier for sandbox management
        project_id: Project identifier for sandbox management
        config: Optional configuration dictionary

    Returns:
        Configured CommandTools instance
    """
    if config is None:
        config = {}

    return CommandTools(
        user_id=user_id,
        project_id=project_id,
        default_timeout=config.get("default_timeout", 60),
        max_output_size=config.get("max_output_size", 1024 * 1024),
    )


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("CommandTools v2 - Enhanced E2B Sandbox Command Operations")
    print("Available classes: CommandTools, ProcessInfo, CommandResult, ServiceInfo")
    print("Available functions: create_command_tools")
    print("\nKey features:")
    print("  - run_command: Execute simple shell commands")
    print("  - run_service: Start long-running services (servers, React dev, etc.)")
    print("  - list_processes: List all running processes")
    print("  - kill_process: Kill a process by PID")
    print("  - send_stdin: Send input to a process")
    print("  - get_service_url: Get public URL for a service on a port")
    print("\nReady for production use with Agno agents!")
