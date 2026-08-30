import uuid

from .input import UserInput
from .messages import ActionMessageBox, BaseMessageBox, MessageBox
from .slash_commands import BaseSlashCommand, SlashCommandSuggest
from .status import StatusBar
from textual.app import ComposeResult
from textual.containers import Vertical

from microclaw.channels.tui.ui.enums import RoleEnum


class ChatWidget(Vertical):
    def __init__(
        self,
        channel: "TUIChannel",  # noqa: F821
        commands: list[BaseSlashCommand] | None = None,
    ):
        super().__init__()
        self._channel = channel
        self._mode = "home"
        self._messages_container = Vertical(id="messages_container")
        self._queued_container = Vertical(id="queued_container")
        self._slash_suggest = SlashCommandSuggest(commands=commands, id="slash_suggest")
        self._user_input = UserInput(
            channel=self._channel,
            chat=self,
            slash_suggest=self._slash_suggest,
            placeholder="Ask...",
            id="user_input",
        )
        self._input_container = Vertical(
            self._slash_suggest,
            self._user_input,
            id="input_container",
        )
        self._status_bar = StatusBar(id="status_bar")
        self._bottom_container: Vertical | None = None

        self._last_message: BaseMessageBox | None = None

    @property
    def status_bar(self) -> StatusBar:
        return self._status_bar

    def compose(self) -> ComposeResult:
        yield self._messages_container
        yield self._queued_container
        self._bottom_container = Vertical(
            self._input_container,
            self._status_bar,
            id="bottom_container",
        )
        yield self._bottom_container

    async def on_mount(self) -> None:
        await self.update_mode(mode="home")
        self._user_input.focus()

    async def update_mode(self, mode: str) -> None:
        self._mode = mode

        if self._bottom_container is None:
            return

        if mode == "home":
            self._messages_container.display = False
            self._queued_container.display = False
            self._bottom_container.styles.height = "100%"
            self._bottom_container.styles.align = ("center", "middle")
            self._bottom_container.styles.dock = None
            self._input_container.styles.width = "75%"
            self._status_bar.display = False
        else:
            self._messages_container.display = True
            self._queued_container.display = True
            self._bottom_container.styles.height = "auto"
            self._bottom_container.styles.align = ("left", "top")
            self._bottom_container.styles.dock = "bottom"
            self._input_container.styles.width = "100%"
            self._status_bar.display = True

    async def add_message(
        self, role: RoleEnum, text: str | None = None
    ) -> MessageBox | None:
        message_box = MessageBox(role=role, text=text)
        await self._messages_container.mount(message_box)
        self._last_message = message_box
        self._messages_container.scroll_end()

        return message_box

    def update_message(self, role: RoleEnum, text: str | None = None) -> None:
        if self._last_message is None or not isinstance(self._last_message, MessageBox):
            return
        self._last_message.update_message(role=role, text=text)
        self._messages_container.scroll_end()

    async def add_confirmation_message(
        self,
        question: str,
        session_id: uuid.UUID,
    ) -> ActionMessageBox | None:
        action_box = ActionMessageBox(
            question=question,
            session_id=session_id,
            channel=self._channel,
        )
        await self._messages_container.mount(action_box)
        self._last_message = action_box
        self._messages_container.scroll_end()

        return action_box

    async def set_queued_messages(self, texts: list[str]) -> None:
        self._queued_container.remove_children()
        for text in texts:
            message_box = MessageBox(
                role=RoleEnum.USER,
                text=f"[dim](queued)[/dim] {text}",
            )
            await self._queued_container.mount(message_box)
        self._queued_container.scroll_end()

    def clear_queued_messages(self) -> None:
        self._queued_container.remove_children()
