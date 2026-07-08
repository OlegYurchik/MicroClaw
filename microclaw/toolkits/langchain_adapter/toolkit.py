import importlib
from typing import Any

from langchain_core.tools import BaseToolkit, BaseTool

from microclaw.toolkits.base import BaseToolKit

from .settings import LangChainToolkitAdapterSettings


class LangChainToolkitAdapter(BaseToolKit[LangChainToolkitAdapterSettings]):
    """Adapter that wraps a LangChain toolkit into the microclaw toolkit format.

    The adapter instantiates a LangChain ``BaseToolkit``, retrieves its tools,
    optionally filters them by name, and applies the toolkit key prefix to each
    tool name so that they integrate seamlessly with the microclaw agent.
    """

    def get_tools(self) -> list[BaseTool]:
        toolkit_cls = self._import_class(self._settings.toolkit_class)

        if not isinstance(toolkit_cls, type) or not issubclass(
            toolkit_cls, BaseToolkit
        ):
            raise TypeError(
                f"Class '{self._settings.toolkit_class}' must be a subclass of "
                f"langchain_core.tools.BaseToolkit"
            )

        lc_toolkit = toolkit_cls(**self._settings.args)
        tools = lc_toolkit.get_tools()

        if self._settings.selected_tools is not None:
            allowed = set(self._settings.selected_tools)
            available = {tool.name for tool in tools}
            for name in allowed:
                if name not in available:
                    raise ValueError(
                        f"Tool '{name}' is not available in the toolkit. "
                        f"Available tools: {sorted(available)}"
                    )
            tools = [tool for tool in tools if tool.name in allowed]

        for tool in tools:
            tool.name = self.prefix + tool.name

        return tools

    @staticmethod
    def _import_class(dotted_path: str) -> Any:
        module_path, class_name = dotted_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        if not hasattr(module, class_name):
            raise ValueError(
                f"Toolkit class '{class_name}' not found in module '{module_path}'"
            )
        return getattr(module, class_name)
