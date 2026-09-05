import asyncio

import typer

from microclaw.agents import Agent
from microclaw.channels.tui import TUIChannel, TUIChannelSettings
from microclaw.resolver import DependencyResolver
from microclaw.sessions_storages import get_sessions_storage
from microclaw.settings import MicroclawSettings
from microclaw.syncers import get_syncer
from microclaw.users_storages import get_users_storage
from microclaw.utils import get_by_key_or_first


async def _resolve_tui_channel_deps(
    settings: MicroclawSettings,
    agent_name: str | None = None,
) -> tuple[DependencyResolver, Agent, object, object, object]:
    """Shared async helper that resolves and validates all TUI channel dependencies."""
    resolver = DependencyResolver(settings=settings)

    agent_settings = get_by_key_or_first(storage=settings.agents, key=agent_name)
    if agent_settings is None:
        if settings.agents:
            raise ValueError(f"Agent '{agent_name}' does not exist")
        else:
            raise ValueError("You need to setup agents")

    sessions_storage_settings = get_by_key_or_first(storage=settings.sessions_storages)
    if sessions_storage_settings is None:
        raise ValueError("You need to setup sessions storage")
    users_storage_settings = get_by_key_or_first(storage=settings.users_storages)
    if users_storage_settings is None:
        raise ValueError("You need to setup users storage")

    agents = await resolver.resolve_agents()
    agent = get_by_key_or_first(storage=agents, key=agent_name)
    if agent is None:
        raise ValueError(
            f"Agent '{agent_name}' was resolved to None. "
            "Ensure the agent is configured correctly."
        )

    sessions_storage = get_sessions_storage(settings=sessions_storage_settings)
    users_storage = get_users_storage(settings=users_storage_settings)
    syncer = get_syncer(settings=settings.syncer)
    return resolver, agent, sessions_storage, users_storage, syncer


def create_tui_channel(
    settings: MicroclawSettings,
    agent_name: str | None = None,
    debug: bool = False,
) -> TUIChannel:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        import nest_asyncio
        nest_asyncio.apply()

    resolver, agent, sessions_storage, users_storage, syncer = asyncio.run(
        _resolve_tui_channel_deps(settings, agent_name)
    )
    return TUIChannel(
        settings=TUIChannelSettings(
            debug=debug,
        ),
        agent=agent,
        sessions_storage=sessions_storage,
        users_storage=users_storage,
        resolver=resolver,
        syncer=syncer,
    )


async def _run_tui(
    settings: MicroclawSettings,
    agent_name: str | None,
    debug: bool,
) -> None:
    resolver, agent, sessions_storage, users_storage, syncer = await _resolve_tui_channel_deps(
        settings, agent_name
    )
    channel = TUIChannel(
        settings=TUIChannelSettings(
            debug=debug,
        ),
        agent=agent,
        sessions_storage=sessions_storage,
        users_storage=users_storage,
        resolver=resolver,
        syncer=syncer,
    )
    await channel.run()


def run(
    ctx: typer.Context,
    agent_name: str | None = typer.Argument(default=None, metavar="name"),
    debug: bool = typer.Option(False, "-d", "--debug", metavar="debug"),
):
    settings: MicroclawSettings = ctx.obj["settings"]
    asyncio.run(_run_tui(settings, agent_name, debug))


def callback(ctx: typer.Context) -> None:
    pass


def get_cli() -> typer.Typer:
    cli = typer.Typer()

    cli.callback()(callback)
    cli.command(name="run")(run)

    return cli
