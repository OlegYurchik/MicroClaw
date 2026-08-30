from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option


class SelectModal(ModalScreen[str | None]):
    """Generic modal screen for selecting an item from a list."""

    def __init__(
        self,
        title: str,
        items: dict[str, str],
        current_key: str = "",
        modal_id: str = "select_modal",
        list_id: str = "select_list",
    ) -> None:
        super().__init__()
        self._title = title
        self._items = items
        self._current_key = current_key
        self._modal_id = modal_id
        self._list_id = list_id

    def compose(self) -> ComposeResult:
        with Vertical(id=self._modal_id):
            yield Static(self._title, id=f"{self._modal_id}_title")
            options = [Option(label, id=key) for key, label in self._items.items()]
            yield OptionList(*options, id=self._list_id)

    def on_mount(self) -> None:
        option_list = self.query_one(f"#{self._list_id}", OptionList)
        for idx, key in enumerate(self._items):
            if key == self._current_key:
                option_list.highlighted = idx
                break

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option_id)

    def key_escape(self) -> None:
        self.dismiss(None)
