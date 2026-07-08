import difflib
from typing import Any

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.fabric import get_toolkit
from microclaw.toolkits import ToolKitSettings
from .dto import ToolKitInfo, ToolInfo
from .settings import DynamicLoaderToolKitSettings


class DynamicLoaderToolKit(BaseToolKit[DynamicLoaderToolKitSettings]):
    """Toolkit for dynamically loading and using other toolkits."""

    def __init__(self, key: str, settings: ToolKitSettings):
        super().__init__(key=key, settings=settings)
        self._loaded_toolkits: dict[str, BaseToolKit] = {}

    def _calculate_similarity(self, query: str, text: str) -> float:
        matcher = difflib.SequenceMatcher(None, query.lower(), text.lower())
        return matcher.ratio()

    @tool
    async def search_toolkits(self, description: str) -> list[ToolKitInfo]:
        """
        Search for available toolkits by description.

        Args:
            description: Description or keywords to search for in toolkit descriptions

        Returns:
            List of ToolKitInfo objects matching the search criteria, sorted by relevance
        """
        results_with_scores = []

        for toolkit_name, toolkit_config in self._settings.toolkits.items():
            toolkit = self._load_toolkit(toolkit_name, toolkit_config)
            toolkit_description = toolkit.description or ""

            name_score = self._calculate_similarity(description, toolkit_name)
            desc_score = self._calculate_similarity(description, toolkit_description)
            max_score = max(name_score, desc_score)

            if max_score > 0:
                tools = toolkit.get_tools()
                results_with_scores.append(
                    (
                        max_score,
                        ToolKitInfo(
                            name=toolkit_name,
                            description=toolkit_description,
                            tools=[tool.name for tool in tools],
                        ),
                    )
                )

        results_with_scores.sort(key=lambda x: x[0], reverse=True)
        return [info for _, info in results_with_scores]

    @tool
    async def list_toolkits(self) -> list[ToolKitInfo]:
        """
        List all available toolkits.

        Returns:
            List of ToolKitInfo objects for all available toolkits
        """
        results = []

        for toolkit_name, toolkit_config in self._settings.toolkits.items():
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
        """
        Get all tools from a specific toolkit.

        Args:
            toolkit_name: Name of the toolkit to get tools from

        Returns:
            List of ToolInfo objects for all tools in the toolkit
        """
        if toolkit_name not in self._settings.toolkits:
            raise ValueError(
                f"Toolkit '{toolkit_name}' not found in available toolkits"
            )

        toolkit = self._load_toolkit(
            toolkit_name, self._settings.toolkits[toolkit_name]
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
        """
        Call a specific tool from a loaded toolkit.

        Args:
            toolkit_name: Name of the toolkit containing the tool
            tool_name: Name of the tool to call (without prefix)
            **kwargs: Arguments to pass to the tool

        Returns:
            Result of the tool call as a string
        """
        if toolkit_name not in self._settings.toolkits:
            raise ValueError(
                f"Toolkit '{toolkit_name}' not found in available toolkits"
            )

        toolkit = self._load_toolkit(
            toolkit_name, self._settings.toolkits[toolkit_name]
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
