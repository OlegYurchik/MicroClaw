import uuid

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button

from microclaw.channels.cli.ui.enums import RoleEnum
from microclaw.sessions_storages.filters import MessageFilter
from pydantic_filters.pagination import OffsetPagination as BasePagination
from .input import UserInput
from .messages import BaseMessageBox, MessageBox, ActionMessageBox
from .stats import StatsWidget


class ChatWidget(Vertical):
    def __init__(
            self,
            channel: "CLIChannel",  # noqa: F821
    ):
        super().__init__()
        self._channel = channel
        self._mode = "home"
        self._messages_container = Vertical(id="messages_container")
        self._sessions_container = Vertical(id="sessions_container")
        self._user_input = UserInput(
            channel=self._channel,
            chat=self,
            placeholder="Ask...",
            id="user_input",
        )
        self._stats_widget = StatsWidget(id="stats_widget")

        self._last_message: BaseMessageBox | None = None

    @property
    def stats_widget(self) -> StatsWidget:
        return self._stats_widget

    def compose(self) -> ComposeResult:
        yield self._sessions_container
        yield self._messages_container
        with Vertical(id="bottom_container"):
            yield self._user_input
            yield self._stats_widget

    async def on_mount(self) -> None:
        await self.update_mode(mode="home")
        self._user_input.focus()

    def on_resize(self) -> None:
        if self._mode == "home" and self._sessions_container.children:
            self._adjust_button_heights()

    def _adjust_button_heights(self) -> None:
        available_height = self._sessions_container.region.height - 2
        num_buttons = len(self._sessions_container.children)
        optimal_height = min(5, max(3, available_height // num_buttons))
        for button in self._sessions_container.children:
            button.styles.height = optimal_height

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "new_session":
            self._channel._session_id = None
            await self._messages_container.remove_children()
            await self.update_mode(mode="chat")
            return
        
            if event.button.id and event.button.id.startswith("session_"):
                session_id = getattr(event.button, '_session_id', None)
                if session_id:
                    self._channel._session_id = session_id
                    
                    await self._messages_container.remove_children()
                    messages = []
                    async for message in self._channel._sessions_storage.get_messages(filter=MessageFilter(session_id=session_id)):
                        messages.append(message)
                
                for message in messages:
                    role = RoleEnum.USER if message.role == "user" else (RoleEnum.SYSTEM if message.role == "system" else RoleEnum.AI)
                    await self.add_message(role=role, text=message.text)
                
                await self.update_mode(mode="chat")

    async def update_mode(self, mode: str) -> None:
        self._mode = mode

        self._sessions_container.display = mode == "home"
        self._messages_container.display = mode == "chat"

        if mode == "home":
            self._sessions_container.remove_children()

            sessions = []
            sessions_storage = self._channel.get_sessions_storage()
            sessions_ids = []
            async for session_id in sessions_storage.get_sessions():
                sessions_ids.append(session_id)
            sessions_ids = sessions_ids[-3:]
            # TODO: Now getting last message, but need first - need to change sessions_storage method
            sessions_messages = {
                session_id: message
                for session_id in sessions_ids
                async for message in sessions_storage.get_messages(
                    filter=MessageFilter(session_id=session_id),
                    pagination=BasePagination(limit=1, offset=0),
                    from_last_summarization=False,
                )
            }

            for session_id, message in sessions_messages.items():
                if message.text is None:
                    continue
                button_text = message.text[:50] + "..." if len(message.text) > 50 else message.text
                button_id = f"session_{session_id.hex}"
                button = Button(button_text, id=button_id)
                button._session_id = session_id
                await self._sessions_container.mount(button)

            self._adjust_button_heights()

    async def _remove_old_message_if_needed(self) -> None:
        if self._last_message is not None and self._last_message.remove_allowed:
            await self._last_message.remove()
            self._last_message = None

    async def add_message(self, role: RoleEnum, text: str | None = None) -> MessageBox | None:
        await self._remove_old_message_if_needed()
        message_box = MessageBox(role=role, text=text)
        await self._messages_container.mount(message_box)
        self._last_message = message_box
        self._messages_container.scroll_end()

        return message_box

    async def update_message(self, role: RoleEnum, text: str | None = None) -> None:
        if self._last_message is None or not isinstance(self._last_message, MessageBox):
            return
        self._last_message.update_message(role=role, text=text)
        self._messages_container.scroll_end()

    async def add_confirmation_message(
            self,
            question: str,
            session_id: uuid.UUID,
            confirmation_id: uuid.UUID,
    ) -> ActionMessageBox | None:
        await self._remove_old_message_if_needed()
        action_box = ActionMessageBox(
            question=question,
            session_id=session_id,
            confirmation_id=confirmation_id,
            channel=self._channel,
        )
        await self._messages_container.mount(action_box)
        self._last_message = action_box
        self._messages_container.scroll_end()

        return action_box

