from .select import SelectModal


class AgentSelectModal(SelectModal):
    def __init__(self, agents: dict[str, str], current_agent_key: str = "") -> None:
        super().__init__(
            title="Select an agent",
            items=agents,
            current_key=current_agent_key,
            modal_id="agent_modal",
            list_id="agent_list",
        )
