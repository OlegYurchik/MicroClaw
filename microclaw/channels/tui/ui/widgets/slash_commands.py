import datetime

from textual.widgets import OptionList
from textual.widgets.option_list import Option

from microclaw.channels.tui.ui.enums import RoleEnum


class BaseSlashCommand:
    NAME: str = ""
    DESCRIPTION: str = ""
    ALIASES: list[str] = []

    def matches(self, query: str) -> bool:
        if not query.startswith("/"):
            return False
        query = query.lower()
        names = [self.NAME] + [a for a in self.ALIASES]
        return any(name.startswith(query) for name in names)

    async def execute(self, ctx: "SlashCommandContext") -> None:  # noqa: F821
        raise NotImplementedError


class ExitCommand(BaseSlashCommand):
    NAME = "/exit"
    DESCRIPTION = "Exit the application"
    ALIASES = ["/quit"]

    async def execute(self, ctx: "SlashCommandContext") -> None:  # noqa: F821
        await ctx.app.add_message(role=RoleEnum.SYSTEM, text="Goodbye!")
        ctx.app.exit()


DEFAULT_SLASH_COMMANDS: list[BaseSlashCommand] = [
    ExitCommand(),
]


class SlashCommandSuggest(OptionList):
    def __init__(
        self,
        commands: list[BaseSlashCommand] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._commands = commands or DEFAULT_SLASH_COMMANDS
        self.display = False

    def update_suggestions(self, prefix: str) -> None:
        results = [cmd for cmd in self._commands if cmd.matches(prefix)]
        self.clear_options()
        for cmd in results:
            self.add_option(
                Option(
                    prompt=f"{cmd.NAME}  [dim]{cmd.DESCRIPTION}[/dim]",
                    id=cmd.NAME,
                )
            )
        self.display = bool(results)
        if results:
            self.highlighted = 0

    def get_selected_command(self) -> BaseSlashCommand | None:
        if self.highlighted is None:
            return None
        option = self.get_option_at_index(self.highlighted)
        for cmd in self._commands:
            if cmd.NAME == option.id:
                return cmd
        return None


def format_time_ago(timestamp: datetime.datetime) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
    diff = now - timestamp
    if diff < datetime.timedelta(seconds=0):
        return "just now"
    if diff < datetime.timedelta(minutes=1):
        return f"{int(diff.total_seconds())}s ago"
    if diff < datetime.timedelta(hours=1):
        return f"{int(diff.total_seconds() // 60)}m ago"
    if diff < datetime.timedelta(days=1):
        return f"{int(diff.total_seconds() // 3600)}h ago"
    return f"{int(diff.days)}d ago"
