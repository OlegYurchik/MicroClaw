from typing import Any

from .dto import ToolInfo, ToolKitInfo
from .settings import DynamicLoaderToolKitSettings

from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import DiscoveryCapability, ToolKitCapability
from microclaw.toolkits.fabric import get_toolkit


class DynamicLoaderToolKit(BaseToolKit[DynamicLoaderToolKitSettings]):
    """Toolkit for dynamically loading and using other toolkits."""

    required_capabilities: list[ToolKitCapability] = []
    write_capabilities: list[ToolKitCapability] = []
    discovery_capabilities: list[DiscoveryCapability] = []

    def __init__(self, key: str, settings: ToolKitSettings):
        super().__init__(key=key, settings=settings)
        self._loaded_toolkits: dict[str, BaseToolKit] = {}

    @tool
    async def list_toolkits(self) -> list[ToolKitInfo]:
        """List all available toolkits."""
        results = []

        for toolkit_name, toolkit_config in self._arguments.toolkits.items():
            toolkit = self._load_toolkit(toolkit_name, toolkit_config)
            tools = toolkit.get_tools()
            results.append(
                ToolKitInfo(
                    name=toolkit_name,
                    description=toolkit.description,
                    tools=[tool.name for tool in tools],
                )
            )

        return results

    @tool
    async def load_tools(self, toolkit_name: str) -> list[ToolInfo]:
        """Get all tools from a specific toolkit."""
        if toolkit_name not in self._arguments.toolkits:
            raise ValueError(
                f"Toolkit '{toolkit_name}' not found in available toolkits"
            )

        toolkit = self._load_toolkit(
            toolkit_name, self._arguments.toolkits[toolkit_name]
        )
        tools = toolkit.get_tools()

        return [
            ToolInfo(
                name=tool.name,
                description=tool.description,
            )
            for tool in tools
        ]

    @tool
    async def call_tool(
        self,
        toolkit_name: str,
        tool_name: str,
        **kwargs: Any,
    ) -> str:
        """Call a specific tool from a loaded toolkit."""
        if toolkit_name not in self._arguments.toolkits:
            raise ValueError(
                f"Toolkit '{toolkit_name}' not found in available toolkits"
            )

        toolkit = self._load_toolkit(
            toolkit_name, self._arguments.toolkits[toolkit_name]
        )

        expected_tool_name = f"{toolkit_name}_{tool_name}"
        tool = None
        for t in toolkit.get_tools():
            if t.name == expected_tool_name:
                tool = t
                break

        if tool is None:
            raise ValueError(
                f"Tool '{tool_name}' not found in toolkit '{toolkit_name}'"
            )

        return await tool.ainvoke(input=kwargs)

    def _load_toolkit(self, name: str, config: ToolKitSettings | str) -> BaseToolKit:
        if name in self._loaded_toolkits:
            return self._loaded_toolkits[name]

        toolkit = get_toolkit(key=name, toolkit_settings_or_path=config)
        self._loaded_toolkits[name] = toolkit
        return toolkit
