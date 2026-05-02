import asyncio

import typer

from microclaw.sessions_storages import get_sessions_storage
from microclaw.syncers import get_syncer
from microclaw.users_storages import get_users_storage
from microclaw.utils import get_by_key_or_first


def run(
        ctx: typer.Context,
        agent_name: str | None = typer.Argument(default=None, metavar="name"),
        show_loader: bool = typer.Option(False, "-l", "--loader", metavar="loader"),
        show_costs: bool = typer.Option(False, "-c", "--costs", metavar="costs"),
        show_context_usage: bool = typer.Option(
            False,
            "--context-usage",
            metavar="context_usage",
        ),
        debug: bool = typer.Option(False, "-d", "--debug", metavar="debug"),
):
    from microclaw.channels.cli import CLIChannel, CLIChannelSettings
    from microclaw.resolver import DependencyResolver
    from microclaw.settings import MicroclawSettings

    settings: MicroclawSettings = ctx.obj["settings"]

    resolver = DependencyResolver(settings=settings)

    agent_settings = get_by_key_or_first(storage=settings.agents, key=agent_name)
    if agent_settings is None:
        if settings.agents:
            raise ValueError(f"Agent with name '{agent_name}' not exists")
        else:
            raise ValueError("You need to setup agents")

    sessions_storage_settings = get_by_key_or_first(storage=settings.sessions_storages)
    if sessions_storage_settings is None:
        raise ValueError("You need to setup sessions storage")
    users_storage_settings = get_by_key_or_first(storage=settings.users_storages)
    if users_storage_settings is None:
        raise ValueError("You need to setup users storage")

    agents = asyncio.run(resolver.resolve_agents())
    agent = get_by_key_or_first(storage=agents, key=agent_name)
    sessions_storage = get_sessions_storage(settings=sessions_storage_settings)
    users_storage = get_users_storage(settings=users_storage_settings)
    syncer = get_syncer(settings=settings.syncer)
    channel = CLIChannel(
        settings=CLIChannelSettings(
            show_loader=show_loader,
            show_costs=show_costs,
            show_context_usage=show_context_usage,
            debug=debug,
        ),
        agent=agent,
        sessions_storage=sessions_storage,
        users_storage=users_storage,
        resolver=resolver,
        syncer=syncer,
    )

    asyncio.run(channel.run())


def get_cli() -> typer.Typer:
    cli = typer.Typer()

    cli.command(name="run")(run)

    return cli
