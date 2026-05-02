import asyncio
import pathlib

import typer
from loguru import logger

from .agents import get_cli as get_agents_cli
from .cron import get_cli as get_cron_cli
from .service import MicroclawService
from .settings import MicroclawSettings


def callback(
        ctx: typer.Context,
        env_path: pathlib.Path | None = typer.Option(
            None,
            "--env", "-e",
            help="Environment variables file location",
        ),
        config_path: pathlib.Path | None = typer.Option(
            None,
            "--config", "-c",
            help="Config file location",
        ),
):
    ctx.obj = {}

    settings = MicroclawSettings.load(
        env_prefix="MICROCLAW__",
        env_file=env_path,
        config_file=config_path,
    )
    ctx.obj["settings"] = settings
    
    logger.remove()
    if settings.logging.console:
        logger.add(
            sink=lambda msg: print(msg, end=""),
            level=settings.logging.level,
            format=settings.logging.format,
        )
    if settings.logging.path:
        logger.add(
            sink=settings.logging.path,
            level=settings.logging.level,
            format=settings.logging.format,
            rotation=settings.logging.rotation,
            retention=settings.logging.retention,
            compression=settings.logging.compression,
        )


def run(ctx: typer.Context):
    settings: MicroclawSettings = ctx.obj["settings"]

    microclaw_service = MicroclawService(settings=settings)

    asyncio.run(microclaw_service.run())


def get_cli() -> typer.Typer:
    cli = typer.Typer()

    cli.callback()(callback)
    cli.command(name="run")(run)
    cli.add_typer(get_agents_cli(), name="agents")
    cli.add_typer(get_cron_cli(), name="cron")

    return cli
