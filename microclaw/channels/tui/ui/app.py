import uuid

from .enums import RoleEnum
from .widgets import ActionMessageBox, ChatWidget, MessageBox
from textual.app import App, ComposeResult


class TUIApp(App):
    CSS_PATH = "ui.tcss"

    def __init__(
        self,
        channel: "TUIChannel",  # noqa: F821
    ):
        super().__init__()
        self._channel = channel
        self._chat_widget = ChatWidget(channel=channel, commands=channel.slash_commands)

    async def on_mount(self) -> None:
        if (
            hasattr(self._channel, "_session_id")
            and self._channel._session_id is not None
        ):
            await self._channel.print_spent()

    def compose(self) -> ComposeResult:
        yield self._chat_widget

    def update_stats(
        self,
        context_usage: float | None = None,
        cost: float | None = None,
        currency: str = "$",
    ) -> None:
        self._chat_widget.status_bar.update_stats(
            usage=context_usage,
            cost=cost,
            currency=currency,
        )

    async def add_message(self, role: RoleEnum, text: str | None = None) -> MessageBox:
        return await self._chat_widget.add_message(role=role, text=text)

    def update_message(self, role: RoleEnum, text: str | None = None) -> None:
        self._chat_widget.update_message(role=role, text=text)

    async def add_confirmation_message(
        self,
        question: str,
        session_id: uuid.UUID,
    ) -> ActionMessageBox:
        return await self._chat_widget.add_confirmation_message(
            question=question,
            session_id=session_id,
        )

    async def load_session_messages(self, messages: list) -> None:
        for message in messages:
            role = RoleEnum.USER if message.role == "user" else RoleEnum.AI
            await self._chat_widget.add_message(role=role, text=message.text)

    async def set_queued_messages(self, texts: list[str]) -> None:
        await self._chat_widget.set_queued_messages(texts)

    def clear_queued_messages(self) -> None:
        self._chat_widget.clear_queued_messages()

    def show_thinking(self) -> None:
        self._chat_widget.status_bar.show_thinking()

    def hide_thinking(self) -> None:
        self._chat_widget.status_bar.hide_thinking()
