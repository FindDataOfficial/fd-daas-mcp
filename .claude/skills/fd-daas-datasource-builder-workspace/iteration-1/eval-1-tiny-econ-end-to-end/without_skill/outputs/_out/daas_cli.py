#!/usr/bin/env python3
"""daas_cli.py - Click sidecar CLI for the tiny_econ library.

Exposes one Click command per data-fetching function in tiny_econ.api that
does NOT already carry a @click.command decorator. The original library
already wraps `fetch_holidays` with @click.command("holidays"), so it is
intentionally NOT re-wrapped here.

Each command takes the function's parameters as Click options and prints the
result as JSON records (one JSON array) to stdout.

IMPORTANT: tiny_econ's api.example.com endpoints are unreachable by design.
This CLI imports and calls the real functions; running it will raise on the
network call. It is a structural wrapper (sidecar) for daas dispatch, not a
live-data tool.

Usage:
    python daas_cli.py get-cpi-series --country CN --start-year 2010 --end-year 2024
    python daas_cli.py fetch-gdp-quarterly --country US
    python daas_cli.py list-countries
"""
from __future__ import annotations

import json
import sys
from typing import Any

import click

try:
    from tiny_econ import api as tiny_econ_api
except ImportError as exc:  # pragma: no cover
    click.echo(
        f"ERROR: could not import tiny_econ.api ({exc}). "
        "Install the tiny_econ package (pip install -e <path-to-tiny_econ>) "
        "or ensure it is on PYTHONPATH.",
        err=True,
    )
    sys.exit(2)


def _emit_records(records: Any) -> None:
    """Print records as a JSON array to stdout.

    - pandas.DataFrame -> df.to_dict(orient="records")
    - list/tuple -> as-is
    - dict -> wrapped in a single-element list
    - other -> wrapped as [{"value": <obj>}]
    """
    # DataFrame duck-typing without a hard pandas dependency at import time
    if hasattr(records, "to_dict") and callable(records.to_dict):
        try:
            rows = records.to_dict(orient="records")
        except Exception:
            rows = records.to_dict(orient="records")
    elif isinstance(records, (list, tuple)):
        rows = list(records)
    elif isinstance(records, dict):
        rows = [records]
    else:
        rows = [{"value": records}]
    click.echo(json.dumps(rows, ensure_ascii=False, default=str))


@click.group(help="tiny_econ daas sidecar CLI (one command per unwrapped fetcher).")
def cli() -> None:
    """Entry group."""


# --- get_cpi_series -------------------------------------------------------
@cli.command("get-cpi-series")
@click.option("--country", default="CN", show_default=True, help="ISO alpha-2 country code, e.g. CN / US.")
@click.option("--start-year", type=int, default=2010, show_default=True, help="Start year (inclusive).")
@click.option("--end-year", type=int, default=2024, show_default=True, help="End year (inclusive).")
def get_cpi_series(country: str, start_year: int, end_year: int) -> None:
    """Fetch CPI year-over-year series (monthly) as JSON records.

    Columns: date, cpi_yoy, country.
    """
    df = tiny_econ_api.get_cpi_series(country=country, start_year=start_year, end_year=end_year)
    _emit_records(df)


# --- fetch_gdp_quarterly --------------------------------------------------
@cli.command("fetch-gdp-quarterly")
@click.option("--country", default="US", show_default=True, help="ISO alpha-2 country code.")
def fetch_gdp_quarterly(country: str) -> None:
    """Fetch quarterly GDP (current USD + YoY growth) as JSON records.

    Columns: date, gdp_current_usd, gdp_growth_yoy, country.
    """
    df = tiny_econ_api.fetch_gdp_quarterly(country=country)
    _emit_records(df)


# --- list_countries -------------------------------------------------------
@cli.command("list-countries")
def list_countries() -> None:
    """List all supported country codes as JSON records.

    Columns: code, name.
    """
    records = tiny_econ_api.list_countries()
    _emit_records(records)


# NOTE: fetch_holidays is intentionally NOT wrapped here because the original
# tiny_econ.api already decorates it with @click.command("holidays").
# To use it, invoke the library's own CLI directly:
#   python -m tiny_econ holidays --market US


if __name__ == "__main__":
    cli()
