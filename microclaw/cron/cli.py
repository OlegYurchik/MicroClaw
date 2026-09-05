import asyncio

import typer


async def _run(ctx: typer.Context):
    # Inline imports avoid a circular dependency: cron -> resolver -> cron
    from microclaw.cron.service import CronService
    from microclaw.resolver import DependencyResolver
    from microclaw.settings import MicroclawSettings

    settings: MicroclawSettings = ctx.obj["settings"]

    resolver = DependencyResolver(settings=settings)

    crons = await resolver.resolve_crons()
    if not crons:
        raise ValueError("You need to setup cron tasks")

    service = CronService(crons=crons)

    await service.run()


def run(ctx: typer.Context):
    asyncio.run(_run(ctx))


def get_cli() -> typer.Typer:
    cli = typer.Typer()

    cli.command(name="run")(run)

    return cli
