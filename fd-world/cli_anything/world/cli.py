"""
CLI entry point for cli-anything-daas.

Click-based CLI with --json flag, commands: list-sources, search, categories,
describe, and REPL mode.
"""
from __future__ import annotations

import sys
import click

from cli_anything.daas.core.registry import (
    list_functions,
    search_functions,
    get_function_info,
    get_categories,
    list_sources,
)
from cli_anything.daas.sources.config import load_sources, get_adapter, SourceConfig
from cli_anything.daas.utils.output import format_output


@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.pass_context
def cli(ctx, json_output):
    """DAAS — Data as a Service: multi-source data access CLI.

    Sources: AKShare, World Bank, CKAN, Chinese National Statistics.
    """
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    if ctx.invoked_subcommand is None:
        # Pass json flag to REPL
        ctx.invoke(repl)


@cli.command()
@click.pass_context
def repl(ctx):
    """Interactive REPL mode"""
    try:
        import prompt_toolkit
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    except ImportError:
        click.echo("REPL mode requires prompt_toolkit. Install: pip install prompt_toolkit")
        click.echo("Falling back to simple input loop.")
        _simple_repl(ctx)
        return

    from pathlib import Path
    hist_path = Path.home() / ".cache" / "cli-anything-daas" / "history"
    hist_path.parent.mkdir(parents=True, exist_ok=True)
    history = FileHistory(str(hist_path))
    session = prompt_toolkit.PromptSession(
        history=history,
        auto_suggest=AutoSuggestFromHistory(),
        message="daas> ",
    )
    click.echo("DAAS REPL — type 'help' for commands, 'exit' to quit")
    click.echo(f"Sources: akshare, worldbank, ckan, cnstats")
    while True:
        try:
            line = session.prompt()
        except (EOFError, KeyboardInterrupt):
            break
        if not line.strip():
            continue
        if line.strip() == "exit":
            break
        if line.strip() == "help":
            _repl_help()
            continue
        _repl_execute(ctx, line.strip())
    click.echo("Goodbye!")


def _repl_help():
    click.echo("Commands:")
    click.echo("  list-sources             List all data sources")
    click.echo("  search <query>            Search functions across all sources")
    click.echo("  categories [source]       List all categories")
    click.echo("  describe <function>       Show function details (params + columns)")
    click.echo("  call <func> [k=v ...]     Call a function with parameters")
    click.echo("  exit                       Exit REPL")
    click.echo("  help                       Show this help")


def _repl_execute(ctx, line):
    parts = line.split()
    cmd = parts[0]
    args = parts[1:]
    json_output = ctx.obj.get("json", False)
    try:
        if cmd == "list-sources":
            _cmd_list_sources(json_output)
        elif cmd == "search":
            if not args:
                click.echo("Usage: search <query>")
                return
            _cmd_search(" ".join(args), json_output)
        elif cmd == "categories":
            source = args[0] if args else None
            _cmd_categories(source, json_output)
        elif cmd == "describe":
            if not args:
                click.echo("Usage: describe <function>")
                return
            _cmd_describe(args[0], json_output)
        elif cmd == "call":
            if not args:
                click.echo("Usage: call <function> [key=value ...]")
                return
            _cmd_call_repl(args[0], args[1:], json_output)
        else:
            click.echo(f"Unknown command: {cmd}. Type 'help'")
    except Exception as e:
        click.echo(f"Error: {e}")


def _simple_repl(ctx):
    click.echo("(simple mode — type 'help' for commands, 'exit' to quit)")
    while True:
        try:
            line = input("daas> ")
        except (EOFError, KeyboardInterrupt):
            break
        if not line.strip():
            continue
        if line.strip() == "exit":
            break
        if line.strip() == "help":
            _repl_help()
            continue
        _repl_execute(ctx, line.strip())
    click.echo("Goodbye!")


# ── CLI commands ──────────────────────────────────────────────────────


@cli.command("list-sources")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.pass_context
def list_sources_cmd(ctx, json_output):
    """List all configured data sources with status."""
    _cmd_list_sources(json_output or ctx.obj.get("json", False))


def _cmd_list_sources(json_output: bool):
    """Shared list-sources implementation for CLI and REPL."""
    import json as j

    configs = load_sources()
    if json_output:
        data = []
        for c in configs:
            data.append({
                "name": c.name,
                "label": c.label,
                "description": c.description,
                "url": c.url,
                "enabled": c.enabled,
                "installed": c.is_installed(),
            })
        click.echo(j.dumps(data, ensure_ascii=False, indent=2))
    else:
        click.echo(f"{'SOURCE':<14} {'LABEL':<22} {'INSTALLED':<10} {'DESCRIPTION'}")
        click.echo("-" * 90)
        for c in configs:
            installed = "yes" if c.is_installed() else "no"
            desc = c.description[:45] + "..." if len(c.description) > 48 else c.description
            click.echo(f"{c.name:<14} {c.label:<22} {installed:<10} {desc}")
        click.echo()
        click.echo("Install missing sources: pip install <package>")


@cli.command("search")
@click.argument("query", nargs=-1, required=True)
@click.option("--source", "-s", help="Filter by source name")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.pass_context
def search_cmd(ctx, query, source, json_output):
    """Search functions by name, category, or description across all sources."""
    json_mode = json_output or (ctx.obj.get("json", False) if ctx.obj else False)
    _cmd_search(" ".join(query), json_mode, source=source)


def _cmd_search(query: str, json_output: bool, source: str | None = None):
    """Shared search implementation."""
    import json as j

    # First try the DB registry
    results = search_functions(query, source=source)

    if not results:
        # Fallback: search from source adapter stubs
        results = _search_from_adapters(query, source)

    if not results:
        click.echo("No matching functions found")
        return

    if json_output:
        click.echo(j.dumps(results, ensure_ascii=False, indent=2, default=str))
    else:
        click.echo(f"Found {len(results)} functions:")
        for func in results:
            src = func.get("source", "?")
            name = func.get("name", "?")
            cat = func.get("category", "")
            desc = func.get("description", "")[:60]
            click.echo(f"  [{src}] {name}  ({cat})")
            if desc:
                click.echo(f"    {desc}")


def _search_from_adapters(query: str, source: str | None = None) -> list[dict]:
    """Fallback search from source adapters when DB is empty."""
    configs = load_sources()
    results = []
    q_lower = query.lower()

    for cfg in configs:
        if source and cfg.name != source:
            continue
        adapter = get_adapter(cfg.name)
        if adapter is None:
            continue
        try:
            funcs = adapter.discover()
        except Exception:
            continue
        for func in funcs:
            name = func.get("name", "")
            cat = func.get("category", "")
            desc = func.get("description", "")
            if q_lower in name.lower() or q_lower in cat.lower() or q_lower in desc.lower():
                results.append(func)
    return results


@cli.command("categories")
@click.option("--source", "-s", help="Filter by source name")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.pass_context
def categories_cmd(ctx, source, json_output):
    """List all function categories with counts."""
    _cmd_categories(source, json_output or ctx.obj.get("json", False))


def _cmd_categories(source: str | None, json_output: bool):
    """Shared categories implementation."""
    import json as j

    cats = get_categories(source=source)

    # Fallback to adapter discovery if DB is empty
    if not cats:
        cats = _categories_from_adapters(source)

    if not cats:
        click.echo("No categories found")
        return

    if json_output:
        click.echo(j.dumps(cats, ensure_ascii=False, indent=2))
    else:
        current_source = None
        for item in cats:
            if item["source"] != current_source:
                current_source = item["source"]
                click.echo(f"\n[{current_source}]")
            click.echo(f"  {item['count']:4d}  {item['category']}")


def _categories_from_adapters(source: str | None = None) -> list[dict]:
    """Build category list from source adapters when DB is empty."""
    configs = load_sources()
    result = []
    for cfg in configs:
        if source and cfg.name != source:
            continue
        adapter = get_adapter(cfg.name)
        if adapter is None:
            continue
        try:
            funcs = adapter.discover()
        except Exception:
            continue
        # Group by category
        cat_counts: dict[str, int] = {}
        for f in funcs:
            cat = f.get("category", "未分类")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        for cat, count in sorted(cat_counts.items()):
            result.append({"source": cfg.name, "category": cat, "count": count})
    return result


def _describe_from_adapters(function: str) -> dict | None:
    """Look up a function from source adapters when DB is empty."""
    configs = load_sources()
    for cfg in configs:
        adapter = get_adapter(cfg.name)
        if adapter is None:
            continue
        try:
            funcs = adapter.discover()
        except Exception:
            continue
        for f in funcs:
            if f.get("name") == function:
                return f
    return None


@cli.command("describe")
@click.argument("function")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.pass_context
def describe_cmd(ctx, function, json_output):
    """Show detailed information about a function (parameters + output columns)."""
    _cmd_describe(function, json_output or ctx.obj.get("json", False))


def _cmd_describe(function: str, json_output: bool):
    """Shared describe implementation."""
    import json as j

    info = get_function_info(function)

    # Fallback to adapter discovery if DB is empty
    if not info:
        info = _describe_from_adapters(function)

    if not info:
        click.echo(f"Function '{function}' not found in registry")
        return

    if json_output:
        click.echo(j.dumps(info, ensure_ascii=False, indent=2))
    else:
        click.echo(f"Function:    {info.get('name', function)}")
        click.echo(f"Source:      {info.get('source', '?')}")
        click.echo(f"Category:    {info.get('category', '')}")
        click.echo(f"Description: {info.get('description', '')}")
        params = info.get("parameters", [])
        if params:
            click.echo("Parameters:")
            for p in params:
                req = "required" if p.get("required") else "optional"
                click.echo(f"  --{p['name']} ({p.get('type', 'str')}, {req})")
                click.echo(f"    {p.get('description', '')}")
        columns = info.get("columns", [])
        if columns:
            click.echo("Output columns:")
            for c in columns[:15]:
                click.echo(f"  {c.get('name', '')}  ({c.get('type', '')}) — {c.get('description', '')}")


# ── Call command ──────────────────────────────────────────────────────


@cli.command("call")
@click.argument("function")
@click.argument("params", nargs=-1)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.pass_context
def call_cmd(ctx, function, params, json_output):
    """Call a data function with key=value parameters.

    Functions are namespaced by source: akshare_*, worldbank_*, ckan_*, cnstats_*
    """
    kwargs = {}
    for p in params:
        if "=" in p:
            k, v = p.split("=", 1)
            kwargs[k] = v

    _cmd_call(function, kwargs, json_output or ctx.obj.get("json", False))


def _cmd_call_repl(function: str, args: list[str], json_output: bool):
    """Call from REPL with raw arg list."""
    kwargs = {}
    for p in args:
        if "=" in p:
            k, v = p.split("=", 1)
            kwargs[k] = v
    _cmd_call(function, kwargs, json_output)


def _cmd_call(function: str, kwargs: dict, json_output: bool):
    """Shared call implementation — routes to correct adapter."""
    from cli_anything.daas.sources.router import SourceRouter
    from cli_anything.daas.core.exceptions import DAASError

    router = SourceRouter()
    try:
        result = router.route(function, **kwargs)
        format_output(result, json_output)
    except DAASError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("help")
def help_cmd():
    """Show help for all commands."""
    _repl_help()


if __name__ == "__main__":
    cli()
