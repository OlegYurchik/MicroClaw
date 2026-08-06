import asyncio

from textual import events, on
from textual.widgets import TextArea

from microclaw.channels.tui.ui.widgets.slash_commands import SlashCommandSuggest


class UserInput(TextArea):
    def __init__(
        self,
        channel: "TUIChannel",  # noqa: F821
        chat,  # noqa: F821
        slash_suggest: SlashCommandSuggest,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._channel = channel
        self._chat = chat
        self._slash_suggest = slash_suggest
        self._selecting_suggestion = False

    async def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            if self._slash_suggest.display:
                event.prevent_default()
                event.stop()
                await self._select_suggestion()
                return
            event.prevent_default()
            event.stop()
            await self._submit_message()
            return

        if event.key == "tab":
            if self._slash_suggest.display:
                event.prevent_default()
                event.stop()
                await self._select_suggestion()
                return
            # Let TextArea handle Tab (focus or indent)
            return

        if event.key == "escape":
            if self._slash_suggest.display:
                event.prevent_default()
                event.stop()
                self._slash_suggest.display = False
                return
            return

        if event.key == "down":
            if self._slash_suggest.display:
                event.prevent_default()
                event.stop()
                self._slash_suggest.action_cursor_down()
                return
            return

        if event.key == "up":
            if self._slash_suggest.display:
                event.prevent_default()
                event.stop()
                self._slash_suggest.action_cursor_up()
                return
            return

        # For all other keys (printable, backspace, delete, arrows without
        # suggestion, etc.) do nothing — TextArea handles them and will post
        # TextArea.Changed after updating its text.

    @on(TextArea.Changed)
    def _on_text_changed(self) -> None:
        if self._selecting_suggestion:
            return
        self._check_suggestions()

    def _check_suggestions(self) -> None:
        text = self.text.strip()
        if text.startswith("/"):
            self._slash_suggest.update_suggestions(text)
        else:
            self._slash_suggest.display = False

    async def _select_suggestion(self) -> None:
        cmd = self._slash_suggest.get_selected_command()
        if cmd is None:
            self._slash_suggest.display = False
            return
        self._slash_suggest.display = False
        self._selecting_suggestion = True
        self.text = cmd.name
        self._selecting_suggestion = False
        await self._submit_message()

    async def _submit_message(self) -> None:
        text = self.text.strip()
        if not text:
            return

        await self._chat.update_mode(mode="chat")
        self.text = ""
        self._slash_suggest.display = False
        asyncio.create_task(self._channel.handle_user_message(text=text))
