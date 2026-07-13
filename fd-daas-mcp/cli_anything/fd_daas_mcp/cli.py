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


def _pdf_branch(argv: list[str]) -> int:
    """In-process cron branches --pdf-ingest / --pdf-search for the optional
    pdf group (mirror daas-mcp/server.py's --run-rule). Reachable as:
    ``python -m cli_anything.fd_daas_mcp.cli --pdf-ingest <path|url>`` /
    ``--pdf-search "<query>"``. Returns a structured error when the [pdf]
    extra is absent."""
    _pdf_dir = Path(__file__).resolve().parents[2] / "pdf-mcp"
    if str(_pdf_dir) not in sys.path:
        sys.path.insert(0, str(_pdf_dir))
    try:
        from pdf_tools import cli_ingest, cli_search  # type: ignore
    except Exception as e:  # noqa: BLE001
        click.echo(json.dumps({"error": f"pdf extra not installed: {e}. uv sync --extra pdf"}))
        return 1
    if "--pdf-ingest" in argv:
        i = argv.index("--pdf-ingest")
        if i + 1 >= len(argv):
            click.echo(json.dumps({"error": "--pdf-ingest requires a <path|url> argument"}))
            return 2
        return cli_ingest(argv[i + 1])
    if "--pdf-search" in argv:
        i = argv.index("--pdf-search")
        if i + 1 >= len(argv):
            click.echo(json.dumps({"error": "--pdf-search requires a <query> argument"}))
            return 2
        return cli_search(argv[i + 1])
    return 0


if __name__ == "__main__":
    if "--pdf-ingest" in sys.argv or "--pdf-search" in sys.argv:
        sys.exit(_pdf_branch(sys.argv[1:]))
    cli()
