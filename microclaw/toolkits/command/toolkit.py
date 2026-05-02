import asyncio
import shutil
from typing import Any, Iterable

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction
from .dto import CommandResult
from .settings import CommandToolKitSettings


class CommandToolKit(BaseToolKit[CommandToolKitSettings]):
    """Tools for executing shell commands with a whitelist of allowed commands."""

    def __init__(self, key: str, settings: CommandToolKitSettings):
        super().__init__(key=key, settings=settings)
        self._allowed_commands_set = set(self._settings.allowed_commands) if self._settings.allowed_commands else None

    def _validate_command(self, command: str) -> str:
        base_command = command.split()[0] if command else ""
        
        if self._allowed_commands_set is not None and base_command not in self._allowed_commands_set:
            raise PermissionError(
                f"Command '{base_command}' is not allowed. "
                f"Allowed commands: {self._settings.allowed_commands}"
            )
        
        command_path = shutil.which(base_command)
        if command_path is None:
            raise RuntimeError(f"Command '{base_command}' not found in system PATH")
        
        return command_path

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

        if self.settings.execute_mode is PermissionModeEnum.DENY:
            raise PermissionError("Command execution denied")
        if self.settings.execute_mode is PermissionModeEnum.REQUEST:
            full_command = f"{command} {' '.join(args)}" if args else command
            confirmation_request_text = f"Execute command: {full_command}?"
            if not await self.request_confirmation(confirmation_request_text):
                raise UserDeniedAction()

        command_path = self._validate_command(command)

        try:
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
            raise RuntimeError(f"Error executing command '{command}': {str(e)}")
