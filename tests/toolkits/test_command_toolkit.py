import asyncio
from unittest.mock import AsyncMock

import pytest

from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.command.dto import CommandResult
from microclaw.toolkits.command.toolkit import CommandToolKit


class TestExecuteCommand:
    @pytest.mark.asyncio
    async def test_success(self):
        settings = ToolKitSettings(
            path="microclaw.toolkits.command.toolkit.CommandToolKit",
            args={
                "allowed_commands": ["echo"],
                "execute_mode": "allow",
            },
        )

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"hello", b""))
        mock_process.returncode = 0

        async def mock_runner(*args, **kwargs):
            return mock_process

        toolkit = CommandToolKit(
            key="command",
            settings=settings,
            subprocess_runner=mock_runner,
        )

        result = await toolkit.execute_command("echo", args=["hello"])

        assert isinstance(result, CommandResult)
        assert result.stdout == "hello"
        assert result.stderr == ""
        assert result.return_code == 0

    @pytest.mark.asyncio
    async def test_denied_mode_raises(self):
        settings = ToolKitSettings(
            path="microclaw.toolkits.command.toolkit.CommandToolKit",
            args={
                "execute_mode": "deny",
            },
        )
        toolkit = CommandToolKit(key="command", settings=settings)

        with pytest.raises(PermissionError, match="denied"):
            await toolkit.execute_command("echo")

    @pytest.mark.asyncio
    async def test_not_in_whitelist_raises(self):
        settings = ToolKitSettings(
            path="microclaw.toolkits.command.toolkit.CommandToolKit",
            args={
                "allowed_commands": ["ls"],
                "execute_mode": "allow",
            },
        )
        toolkit = CommandToolKit(key="command", settings=settings)

        with pytest.raises(PermissionError, match="not allowed"):
            await toolkit.execute_command("echo")

    @pytest.mark.asyncio
    async def test_command_not_found_raises(self):
        settings = ToolKitSettings(
            path="microclaw.toolkits.command.toolkit.CommandToolKit",
            args={
                "allowed_commands": ["nonexistent_command_xyz"],
                "execute_mode": "allow",
            },
        )
        toolkit = CommandToolKit(key="command", settings=settings)

        with pytest.raises(RuntimeError, match="not found"):
            await toolkit.execute_command("nonexistent_command_xyz")

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        settings = ToolKitSettings(
            path="microclaw.toolkits.command.toolkit.CommandToolKit",
            args={
                "allowed_commands": ["sleep"],
                "execute_mode": "allow",
            },
        )

        async def mock_runner(*args, **kwargs):
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_process.kill = AsyncMock()
            mock_process.wait = AsyncMock()
            return mock_process

        toolkit = CommandToolKit(
            key="command",
            settings=settings,
            subprocess_runner=mock_runner,
        )

        with pytest.raises(RuntimeError, match="timed out"):
            await toolkit.execute_command("sleep", args=["10"], timeout=1)

    @pytest.mark.asyncio
    async def test_stderr_output(self):
        settings = ToolKitSettings(
            path="microclaw.toolkits.command.toolkit.CommandToolKit",
            args={
                "allowed_commands": ["echo"],
                "execute_mode": "allow",
            },
        )

        async def mock_runner(*args, **kwargs):
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b"error"))
            mock_process.returncode = 1
            return mock_process

        toolkit = CommandToolKit(
            key="command",
            settings=settings,
            subprocess_runner=mock_runner,
        )

        result = await toolkit.execute_command("echo")
        assert result.stderr == "error"
        assert result.return_code == 1

    @pytest.mark.asyncio
    async def test_no_whitelist_any_command_allowed(self):
        settings = ToolKitSettings(
            path="microclaw.toolkits.command.toolkit.CommandToolKit",
            args={
                "execute_mode": "allow",
            },
        )

        async def mock_runner(*args, **kwargs):
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"ok", b""))
            mock_process.returncode = 0
            return mock_process

        toolkit = CommandToolKit(
            key="command",
            settings=settings,
            subprocess_runner=mock_runner,
        )

        result = await toolkit.execute_command("echo")
        assert result.stdout == "ok"
