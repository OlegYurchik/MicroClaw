from .select import SelectModal


class SessionSelectModal(SelectModal):
    def __init__(self, sessions: dict[str, str], current_session_key: str = "") -> None:
        super().__init__(
            title="Select a session",
            items=sessions,
            current_key=current_session_key,
            modal_id="session_modal",
            list_id="session_list",
        )
