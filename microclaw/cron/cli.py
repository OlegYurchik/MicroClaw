import asyncio

import facet
import typer


def run(ctx: typer.Context):
    from microclaw.resolver import DependencyResolver
    from microclaw.settings import MicroclawSettings

    settings: MicroclawSettings = ctx.obj["settings"]

    resolver = DependencyResolver(settings=settings)

    crons = asyncio.run(resolver.resolve_crons())
    if not crons:
        raise ValueError("You need to setup cron tasks")

    service = facet.AsyncioServiceMixin()
    service.dependencies = crons

    asyncio.run(service.run())


def get_cli() -> typer.Typer:
    cli = typer.Typer()

    cli.command(name="run")(run)

    return cli
