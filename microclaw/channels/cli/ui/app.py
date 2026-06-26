import uuid

from textual.app import App, ComposeResult

from .enums import RoleEnum
from .widgets import ChatWidget, MessageBox, ActionMessageBox


class CLIApp(App):
    CSS_PATH = "ui.tcss"

    def __init__(
            self,
            channel: "CLIChannel",  # noqa: F821
    ):
        super().__init__()
        self._channel = channel
        self._chat_widget = ChatWidget(channel=channel)

    async def on_mount(self) -> None:
        if hasattr(self._channel, '_session_id') and self._channel._session_id is not None:
            await self._channel.print_spent()

    def compose(self) -> ComposeResult:
        yield self._chat_widget

    def update_stats(
            self,
            context_usage: float | None = None,
            cost: float | None = None,
            currency: str = "$",
    ) -> None:
        stats_widget = self._chat_widget.stats_widget
        stats_widget.update_stats(
            usage=context_usage,
            cost=cost,
            currency=currency,
        )

    async def add_message(self, role: RoleEnum, text: str | None = None) -> MessageBox:
        return await self._chat_widget.add_message(role=role, text=text)

    async def update_message(self, role: RoleEnum, text: str | None = None) -> None:
        await self._chat_widget.update_message(role=role, text=text)

    async def add_confirmation_message(
            self,
            question: str,
            session_id: uuid.UUID,
            confirmation_id: uuid.UUID,
    ) -> ActionMessageBox:
        return await self._chat_widget.add_confirmation_message(
            question=question,
            session_id=session_id,
            confirmation_id=confirmation_id,
        )

    async def load_session_messages(self, messages: list) -> None:
        for message in messages:
            role = RoleEnum.USER if message.role == "user" else RoleEnum.AI
            await self._chat_widget.add_message(role=role, text=message.text)
