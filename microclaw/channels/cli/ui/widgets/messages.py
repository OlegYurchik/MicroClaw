import uuid
from microclaw.channels.cli.ui.enums import RoleEnum

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static


class BaseMessageBox(Static):
    def __init__(self, text: str | None = None, remove_allowed: bool = False):
        super().__init__()
        self._text = text
        self._remove_allowed = remove_allowed
        self._text_component = Static(text or "")
        self._panel_component = Horizontal(id="message_panel")

    def compose(self) -> ComposeResult:
        yield self._text_component
        yield self._panel_component

    @property
    def remove_allowed(self) -> bool:
        return self._remove_allowed

    def update_text(self, text: str | None = None) -> None:
        self._text = text
        self._text_component.update(text or "")

    def update_panel(self, widgets: list) -> None:
        self._panel_component.remove_children()
        for widget in widgets:
            self._panel_component.mount(widget)


class MessageBox(BaseMessageBox):
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
        super().__init__(
            text=self._get_display_text(role=role, text=text),
            remove_allowed=text is None,
        )
        self._role = role

    def on_mount(self):
        for role in RoleEnum:
            self.set_class(self._role is role, role.value)

    def update_message(self, role: RoleEnum, text: str | None = None) -> None:
        self._role = role
        self._remove_allowed = text is None

        self.update_text(text=self._get_display_text(role=role, text=text))

    @classmethod
    def _get_display_text(cls, role: RoleEnum, text: str | None) -> str:
        label = cls.LABEL_MAP.get(role)
        label_color = cls.LABEL_COLOR_MAP.get(role)
        if not all((label, label_color)):
            raise ValueError(f"Unsupported role '{role}'")

        content = "[dim]Thinking...[/dim]" if text is None else text
        return f"[bold {label_color}]{label}[/bold {label_color}]: {content}"


class ActionMessageBox(BaseMessageBox):
    CONFIRM_TEXT = "Yes"
    DECLINE_TEXT = "No"
    CONFIRMED_TEXT = "Confirmed"
    DECLINED_TEXT = "Declined"
    CONFIRM_BUTTON_ID = "confirm_button"
    DECLINE_BUTTON_ID = "decline_button"

    def __init__(
        self,
        question: str,
        session_id: uuid.UUID,
        channel: "CLIChannel",  # noqa: F821
    ):
        super().__init__(text=question, remove_allowed=False)
        self._session_id = session_id
        self._channel = channel

    def _get_status_label(self, status_text: str, status_color: str) -> Static:
        return Static(f"[bold {status_color}]{status_text}[/bold {status_color}]")

    def on_mount(self):
        self.set_class(True, "action_message_box")

        confirm_button = Button(
            self.CONFIRM_TEXT,
            id=self.CONFIRM_BUTTON_ID,
            variant="success",
        )
        decline_button = Button(
            self.DECLINE_TEXT,
            id=self.DECLINE_BUTTON_ID,
            variant="error",
        )
        buttons_container = Horizontal(
            confirm_button, decline_button, id="action_buttons"
        )
        self.update_panel([buttons_container])

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        approved = event.button.id == self.CONFIRM_BUTTON_ID

        await self._channel._handle_confirmation_callback(
            session_id=self._session_id,
            approved=approved,
        )

        status_text = self.CONFIRMED_TEXT if approved else self.DECLINED_TEXT
        status_color = "green" if approved else "red"

        status_label = self._get_status_label(status_text, status_color)
        self.update_panel([status_label])
