"""
cli-anything-yfinance — Click CLI for yfinance.

Mirrors cli-anything-akshare: default subcommand enters a REPL; subcommands
search/info/list/categories/call. The proxy subcommand group is omitted
(yfinance does not need the China-network proxy layer akshare uses).
"""
import sys
import click

from cli_anything.yfinance.core.registry import (
    list_functions,
    search_functions,
    get_function_info,
    get_categories,
    get_category_functions,
)
from cli_anything.yfinance.core.runner import call_yfinance_function
from cli_anything.yfinance.utils.output import format_output


@click.group(invoke_without_command=True)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.pass_context
def cli(ctx, json_output):
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    if ctx.invoked_subcommand is None:
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
    hist_path = Path.home() / ".cache" / "cli-anything-yfinance" / "history"
    hist_path.parent.mkdir(parents=True, exist_ok=True)
    history = FileHistory(str(hist_path))
    session = prompt_toolkit.PromptSession(
        history=history,
        auto_suggest=AutoSuggestFromHistory(),
        message="yfinance> ",
    )
    click.echo("yfinance REPL — type 'help' for commands, 'exit' to quit")
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
    click.echo("  list [category]         List all functions or functions in a category")
    click.echo("  search <query>          Search functions by name/category/description")
    click.echo("  info <function>         Show function details")
    click.echo("  categories              List all categories")
    click.echo("  call <func> [k=v ...]   Call a yfinance function with parameters")
    click.echo("  exit                    Exit REPL")
    click.echo("  help                    Show this help")


def _repl_execute(ctx, line):
    parts = line.split()
    cmd = parts[0]
    args = parts[1:]
    json_output = ctx.obj.get("json", False)
    try:
        if cmd == "list":
            cat = args[0] if args else None
            if cat:
                funcs = get_category_functions(cat)
            else:
                funcs = list_functions()
            if not funcs:
                click.echo(f"No functions found")
                return
            for name in sorted(funcs.keys()):
                info = funcs[name]
                click.echo(f"  {name}  ({info.get('category', '')})")
        elif cmd == "search":
            if not args:
                click.echo("Usage: search <query>")
                return
            results = search_functions(" ".join(args))
            if not results:
                click.echo("No results")
                return
            click.echo(f"Found {len(results)} functions:")
            for name, info in results.items():
                click.echo(f"  {name}  ({info.get('category', '')})")
        elif cmd == "info":
            if not args:
                click.echo("Usage: info <function>")
                return
            info = get_function_info(args[0])
            if not info:
                click.echo(f"Function '{args[0]}' not found")
                return
            click.echo(f"Name:        {args[0]}")
            click.echo(f"Category:    {info.get('category', '')}")
            click.echo(f"Description: {info.get('description', '')}")
            click.echo(f"Source:      {info.get('source', '')}")
            params = info.get("parameters", [])
            if params:
                click.echo("Parameters:")
                for p in params:
                    req = "required" if p.get("required") else "optional"
                    click.echo(f"  --{p['name']} ({p.get('type', 'str')}, {req})")
                    click.echo(f"    {p.get('description', '')}")
        elif cmd == "categories":
            cats = get_categories()
            for cat, count in cats.items():
                click.echo(f"  {count:3d}  {cat}")
        elif cmd == "call":
            if not args:
                click.echo("Usage: call <function> [key=value ...]")
                return
            func_name = args[0]
            params = {}
            for p in args[1:]:
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = v
            result = call_yfinance_function(func_name, params)
            format_output(result, json_output)
        else:
            click.echo(f"Unknown command: {cmd}. Type 'help'")
    except SystemExit:
        # runner calls sys.exit on error; swallow it inside the REPL
        pass
    except Exception as e:
        click.echo(f"Error: {e}")


def _simple_repl(ctx):
    click.echo("(simple mode — type 'help' for commands, 'exit' to quit)")
    while True:
        try:
            line = input("yfinance> ")
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


@cli.command()
@click.argument("function")
@click.argument("params", nargs=-1)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def call(function, params, json_output):
    """Call a yfinance function with key=value parameters"""
    kwargs = {}
    for p in params:
        if "=" in p:
            k, v = p.split("=", 1)
            kwargs[k] = v
    result = call_yfinance_function(function, kwargs)
    format_output(result, json_output)


@cli.command("list")
@click.option("--category", "-c", help="Filter by category name")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def list_cmd(category, json_output):
    """List available yfinance functions"""
    import json as j
    if category:
        funcs = get_category_functions(category)
    else:
        funcs = list_functions()
    if not funcs:
        click.echo("No functions found")
        return
    if json_output:
        data = [
            {"name": k, "category": v.get("category", ""), "description": v.get("description", "")}
            for k, v in sorted(funcs.items())
        ]
        click.echo(j.dumps(data, ensure_ascii=False, indent=2))
    else:
        click.echo(f"Total: {len(funcs)} functions")
        for name, info in sorted(funcs.items()):
            click.echo(f"  {name}  ({info.get('category', '')})")


@cli.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def search(query, json_output):
    """Search functions by name, category, or description"""
    import json as j
    q = " ".join(query)
    results = search_functions(q)
    if not results:
        click.echo("No matching functions found")
        return
    if json_output:
        data = [
            {"name": k, "category": v.get("category", ""), "description": v.get("description", "")}
            for k, v in sorted(results.items())
        ]
        click.echo(j.dumps(data, ensure_ascii=False, indent=2))
    else:
        click.echo(f"Found {len(results)} functions:")
        for name, info in sorted(results.items()):
            click.echo(f"  {name}  ({info.get('category', '')})")


@cli.command()
@click.argument("function")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def info(function, json_output):
    """Show detailed information about a function"""
    import json as j
    data = get_function_info(function)
    if not data:
        click.echo(f"Function '{function}' not found")
        return
    if json_output:
        click.echo(j.dumps(data, ensure_ascii=False, indent=2))
    else:
        click.echo(f"Name:        {function}")
        click.echo(f"Category:    {data.get('category', '')}")
        click.echo(f"Description: {data.get('description', '')}")
        click.echo(f"Source:      {data.get('source', '')}")
        params = data.get("parameters", [])
        if params:
            click.echo("Parameters:")
            for p in params:
                req = "required" if p.get("required") else "optional"
                click.echo(f"  --{p['name']} ({p.get('type', 'str')}, {req})")
                click.echo(f"    {p.get('description', '')}")
        columns = data.get("columns", [])
        if columns:
            click.echo("Output columns:")
            for c in columns[:10]:
                click.echo(f"  {c.get('name', '')}")


@cli.command()
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
def categories(json_output):
    """List all function categories with counts"""
    import json as j
    cats = get_categories()
    if json_output:
        data = [{"category": k, "count": v} for k, v in cats.items()]
        click.echo(j.dumps(data, ensure_ascii=False, indent=2))
    else:
        click.echo(f"Total categories: {len(cats)}")
        for cat, count in cats.items():
            click.echo(f"  {count:3d}  {cat}")


if __name__ == "__main__":
    cli()
