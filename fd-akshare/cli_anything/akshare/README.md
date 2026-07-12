# cli-anything-akshare

A command-line interface for [AKShare](https://github.com/akfamily/akshare), the open-source Chinese financial data library.

## Prerequisites

- Python 3.10+
- AKShare library: `pip install akshare`

## Installation

```bash
git clone <this-repo>
cd akshare-agent-harness
pip install -e .
```

## Usage

```bash
# List all available functions
cli-anything-akshare list

# Search for functions
cli-anything-akshare search 历史行情

# Get function details
cli-anything-akshare info stock_zh_a_hist

# Call a function with parameters
cli-anything-akshare call stock_zh_a_hist symbol=000001 start_date=20250101

# JSON output
cli-anything-akshare --json call stock_sse_summary

# Interactive REPL (default)
cli-anything-akshare
```

## Configuration

Set `AKSHARE_REGISTRY` env var to point to a custom registry.json file.

## Testing

```bash
cd tests
pytest -v
```

## Registry

The function metadata registry at `metadata/registry.json` contains 673 functions across 430 categories. This file is auto-generated from the akshare-kit project and can be refreshed with:

```bash
micromamba run -n akshare-kit python -c "
from akshare_kit.generator import generate_registry
generate_registry()
"
```
