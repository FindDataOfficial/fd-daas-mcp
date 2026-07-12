"""Click CLI for fd-daas-mcp - auto-generated from the same registry as the server.

Usage:
  fd-daas-mcp <group> <tool> [key=value ...] [--json]
  fd-daas-mcp                       # REPL mode (needs [repl] extra for history)
  fd-daas-mcp --help                # authoritative live surface (no drift)
"""
from __future__ import annotations

import asyncio
import inspect
import json
import sys
from pathlib import Path
from typing import Any

import click

from cli_anything.fd_daas_mcp import registry


def _parse_value(v: str) -> Any:
    try:
        return json.loads(v)
    except (json.JSONDecodeError, ValueError):
        return v


def _print(result: Any, as_json: bool) -> None:
    if isinstance(result, (dict, list)) or as_json:
        try:
            click.echo(json.dumps(result, default=str, ensure_ascii=False, indent=2))
            return
        except (TypeError, ValueError):
            pass
    click.echo(str(result))


def _make_command(name: str, func: Any) -> click.Command:
    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    help_text = ""
    if func.__doc__:
        help_text = func.__doc__.strip().split("\n\n", 1)[0][:200]

    @click.command(name=name, help=help_text or name)
    @click.argument("kv", nargs=-1)
    @click.option("--json", "as_json", is_flag=True, help="Print raw JSON output")
    def _cmd(kv, as_json):
        kwargs: dict[str, Any] = {}
        for pair in kv:
            if "=" not in pair:
                click.echo(f"error: argument {pair!r} is not key=value", err=True)
                sys.exit(2)
            k, v = pair.split("=", 1)
            kwargs[k] = _parse_value(v)
        for p in params:
            if p.name not in kwargs and p.default is inspect.Parameter.empty:
                click.echo(f"error: missing required parameter {p.name}", err=True)
                sys.exit(2)
        try:
            if inspect.iscoroutinefunction(func):
                result = asyncio.run(func(**kwargs))
            else:
                result = func(**kwargs)
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            click.echo(f"error: {type(e).__name__}: {e}", err=True)
            sys.exit(1)
        _print(result, as_json)

    return _cmd


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """fd-daas-mcp - the consolidated DAAS MCP CLI. Run with no subcommand for REPL."""
    if ctx.invoked_subcommand is None:
        _repl()


def _repl() -> None:
    session = None
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory

        hist = Path.home() / ".cache" / "fd-daas-mcp" / "history"
        hist.parent.mkdir(parents=True, exist_ok=True)
        session = PromptSession(history=FileHistory(str(hist)))
    except ImportError:
        pass
    click.echo("fd-daas-mcp REPL. Ctrl-D to exit. `--help` lists groups/tools.")
    while True:
        try:
            line = (session.prompt("fd-daas-mcp> ") if session else input("fd-daas-mcp> ")).strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("")
            break
        if not line:
            continue
        try:
            cli.main(line.split(), standalone_mode=False)
        except click.exceptions.UsageError as e:
            click.echo(str(e), err=True)
        except SystemExit:
            pass


for _group, _name, _func in registry.build():
    if _group not in cli.commands:
        _grp = click.Group(name=_group, help=f"{_group} group")
        cli.add_command(_grp)
    cli.commands[_group].add_command(_make_command(_name, _func))


if __name__ == "__main__":
    cli()
