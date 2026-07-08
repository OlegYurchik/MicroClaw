from textual import events
from textual.widgets import TextArea

from microclaw.channels.cli.ui.enums import RoleEnum


class UserInput(TextArea):
    def __init__(
        self,
        channel: "CLIChannel",  # noqa: F821
        chat,  # noqa: F821
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

        self._chat.update_mode(mode="chat")

        await self._chat.add_message(role=RoleEnum.USER, text=text)
        self.text = ""
        await self._channel.handle_user_message(text=text)
