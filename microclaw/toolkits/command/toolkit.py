import asyncio
from collections.abc import Awaitable, Callable, Iterable
import shlex
import shutil
from typing import Protocol

from .dto import CommandResult
from .settings import CommandToolKitSettings
from langgraph.types import interrupt

from microclaw.dto import DecisionEnum
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import DiscoveryCapability, ToolKitCapability
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction


class _SubprocessProtocol(Protocol):
    async def communicate(self) -> tuple[bytes, bytes]: ...
    returncode: int | None
    def kill(self) -> None: ...
    async def wait(self) -> int: ...


class CommandToolKit(BaseToolKit[CommandToolKitSettings]):
    """Tools for executing shell commands with a whitelist of allowed commands."""

    required_capabilities: list[ToolKitCapability] = []
    write_capabilities: list[ToolKitCapability] = []
    discovery_capabilities: list[DiscoveryCapability] = []

    def __init__(
        self,
        key: str,
        settings: CommandToolKitSettings,
        subprocess_runner: Callable[..., Awaitable[_SubprocessProtocol]] | None = None,
    ):
        super().__init__(key=key, settings=settings)
        self._allowed_commands_set = (
            set(self._arguments.allowed_commands)
            if self._arguments.allowed_commands
            else None
        )
        self._subprocess_runner = subprocess_runner

    @tool
    async def execute_command(
        self,
        command: str,
        args: Iterable[str] = (),
        timeout: int = 30,
    ) -> CommandResult:
        """
        Execute a shell command with the given arguments.

        Args:
            command: Command to execute (must be in allowed commands list)
            args: List of arguments to pass to the command
            timeout: Maximum execution time in seconds (default: 30)

        Returns:
            CommandResult object with stdout, stderr, and return_code
        """

        if self.arguments.execute_mode is PermissionModeEnum.DENY:
            raise PermissionError("Command execution denied")
        if self.arguments.execute_mode is PermissionModeEnum.REQUEST:
            full_command = f"{command} {' '.join(args)}" if args else command
            confirmation_request_text = f"Execute command: {full_command}?"
            decision = interrupt({"description": confirmation_request_text})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        command_path = self._validate_command(command)

        try:
            if self._subprocess_runner is not None:
                process = await self._subprocess_runner(command_path, *args)
            else:
                process = await asyncio.create_subprocess_exec(
                    command_path,
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            return CommandResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                return_code=process.returncode,
            )
        except asyncio.TimeoutError:
            if process:
                process.kill()
                await process.wait()
            raise RuntimeError(f"Command '{command}' timed out after {timeout} seconds")
        except Exception as e:
            raise RuntimeError(
                f"Error executing command '{command}': {e}"
            ) from e

    def _validate_command(self, command: str) -> str:
        base_command = shlex.split(command)[0] if command else ""

        if (
            self._allowed_commands_set is not None
            and base_command not in self._allowed_commands_set
        ):
            raise PermissionError(
                f"Command '{base_command}' is not allowed. "
                f"Allowed commands: {self._arguments.allowed_commands}"
            )

        command_path = shutil.which(base_command)
        if command_path is None:
            raise RuntimeError(f"Command '{base_command}' not found in system PATH")

        return command_path
