import enum
import uuid

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea
from textual import events


class RoleEnum(str, enum.Enum):
    USER = "user"
    AI = "ai"
    SYSTEM = "system"


class UserInput(TextArea):
    def __init__(
            self,
            channel: "CLIChannel",  # noqa: F821
            chat: "ChatWidget",  # noqa: F821
            **kwargs,
    ):
        super().__init__(**kwargs)
        self._channel = channel
        self._chat = chat

    async def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            await self._submit_message()

    async def _submit_message(self):
        text = self.text.strip()
        if not text:
            return

        await self._chat.add_message(role=RoleEnum.USER, text=text)
        self.text = ""
        self._chat.set_generating(True)
        try:
            await self._channel.handle_user_message(text=text)
        finally:
            self._chat.set_generating(False)


class MessageBox(Static):
    LABEL_MAP = {
        RoleEnum.USER: "You",
        RoleEnum.AI: "AI",
        RoleEnum.SYSTEM: "System",
    }
    LABEL_COLOR_MAP = {
        RoleEnum.USER: "cyan",
        RoleEnum.AI: "green",
        RoleEnum.SYSTEM: "yellow",
    }

    def __init__(self, role: RoleEnum, text: str | None = None) -> None:
        super().__init__()

        self._text = text
        self._role = role
        self._static = Static()

    @property
    def is_generating(self) -> bool:
        return self._text is None

    def compose(self) -> ComposeResult:
        yield self._static

    def on_mount(self):
        for role in RoleEnum:
            self.set_class(self._role is role, role.value)
        self._static.update(self._build_message_text())

    def update_message(self, role: RoleEnum, text: str | None = None) -> None:
        self._role = role
        self._text = text
        self._static.update(self._build_message_text())

    def _build_message_text(self):
        label = self.LABEL_MAP.get(self._role)
        label_color = self.LABEL_COLOR_MAP.get(self._role)
        if not all((label, label_color)):
            raise ValueError(f"Unsupported role '{self._role}'")

        content = "[dim]Thinking...[/dim]" if self._text is None else self._text
        return f"[bold {label_color}]{label}[/bold {label_color}]: {content}"


class StatsWidget(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._context_usage = None
        self._cost = None
        self._currency = "$"

    def update_stats(
            self,
            usage: float | None = None,
            cost: float | None = None,
            currency: str = "$",
    ) -> None:
        self._context_usage = usage
        self._cost = cost
        self._currency = currency

        parts = []
        if self._context_usage is not None:
            parts.append(f"[dim]{self._context_usage:.2f}% context[/dim]")
        if self._cost is not None:
            parts.append(f"[dim]{self._cost:.4f} {self._currency}[/dim]")

        text = " · ".join(parts)
        self.update(text)


class ErrorModal(ModalScreen):
    CLOSE_BUTTON_ID = "close_button"

    def __init__(self, error_message: str):
        super().__init__()
        self._error_message = error_message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Error", id="title")
            yield Static(self._error_message)
            with Horizontal():
                yield Button("Close", id=self.CLOSE_BUTTON_ID, variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == self.CLOSE_BUTTON_ID:
            self.app.pop_screen()


class ConfirmationModal(ModalScreen):
    YES_BUTTON_ID = "yes_button"
    NO_BUTTON_ID = "no_button"

    def __init__(
            self,
            question: str,
            confirmation_id: uuid.UUID,
            channel: "CLIChannel",  # noqa: F821
    ):
        super().__init__()
        self._question = question
        self._confirmation_id = confirmation_id
        self._channel = channel

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Confirmation", id="title")
            yield Static(self._question)
            with Horizontal():
                yield Button("Yes", id=self.YES_BUTTON_ID, variant="success")
                yield Button("No", id=self.NO_BUTTON_ID, variant="error")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        approved = event.button.id == self.YES_BUTTON_ID
        await self._channel.resolve_confirmation(self._confirmation_id, approved)
        self.app.pop_screen()


class ChatWidget(Vertical):
    def __init__(
            self,
            channel: "CLIChannel",  # noqa: F821
    ):
        super().__init__()
        self._channel = channel
        self._messages_container = Vertical(id="messages_container")
        self._user_input = UserInput(
            channel=self._channel,
            chat=self,
            placeholder="Ask...",
            id="user_input",
        )
        self._stats_widget = StatsWidget(id="stats_widget")

        self._last_message_box: MessageBox | None = None
        self._is_generating = False

    @property
    def stats_widget(self) -> StatsWidget:
        return self._stats_widget

    def compose(self) -> ComposeResult:
        yield self._messages_container
        with Vertical(id="bottom_container"):
            yield self._user_input
            yield self._stats_widget

    def on_mount(self) -> None:
        self._user_input.focus()

    def set_generating(self, is_generating: bool) -> None:
        self._is_generating = is_generating
        self._user_input.disabled = is_generating
        if not is_generating:
            self._user_input.focus()
            self._user_input.move_cursor((0, 0))

    async def add_message(self, role: RoleEnum, text: str | None = None) -> None:
        self._last_message_box = MessageBox(role=role, text=text)
        await self._messages_container.mount(self._last_message_box)
        self._messages_container.scroll_end()

    async def update_message(self, role: RoleEnum, text: str | None = None) -> None:
        if self._last_message_box is None:
            return
        self._last_message_box.update_message(role=role, text=text)
        self._messages_container.scroll_end()


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

    def show_error_modal(self, error_message: str) -> None:
        self.push_screen(ErrorModal(error_message))

    def set_generating(self, is_generating: bool) -> None:
        self._chat_widget.set_generating(is_generating)

    async def add_message(self, role: RoleEnum, text: str | None = None) -> None:
        await self._chat_widget.add_message(role=role, text=text)

    async def update_message(self, role: RoleEnum, text: str | None = None) -> None:
        await self._chat_widget.update_message(role=role, text=text)

    def show_confirmation_modal(self, question: str, confirmation_id: uuid.UUID) -> None:
        modal = ConfirmationModal(question, confirmation_id, self._channel)
        self.push_screen(modal)
