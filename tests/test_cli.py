import click
import typer

from microclaw.cli import callback, get_cli
from microclaw.settings import MicroclawSettings


def test_callback_loads_settings():
    ctx = typer.Context(click.Command("test"))
    callback(ctx, env_path=None, config_path=None)

    assert "settings" in ctx.obj
    assert isinstance(ctx.obj["settings"], MicroclawSettings)


def test_callback_with_config_file():
    ctx = typer.Context(click.Command("test"))
    callback(ctx, env_path=None, config_path=None)

    assert "settings" in ctx.obj


def test_get_cli_structure():
    cli = get_cli()
    assert any(cmd.name == "run" for cmd in cli.registered_commands)
    assert any(cmd.name == "cron" for cmd in cli.registered_groups)
    assert any(cmd.name == "tui" for cmd in cli.registered_groups)
