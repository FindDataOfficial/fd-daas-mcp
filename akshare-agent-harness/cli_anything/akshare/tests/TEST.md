# Test Plan: cli-anything-akshare

## Test Inventory

| File | Unit Tests | E2E Tests |
|------|-----------|-----------|
| test_core.py | 8 | 0 |
| test_full_e2e.py | 0 | 6 |

**Total planned tests: 14**

## Unit Test Plan (test_core.py)

### registry.py
- `test_list_functions` — Verify registry loading returns all functions
- `test_search_functions_name` — Search by function name prefix
- `test_search_functions_category` — Search by category name
- `test_search_functions_description` — Search by description text
- `test_get_function_info` — Get details for a known function
- `test_get_categories` — Verify category grouping and counts

### output.py
- `test_format_output_dataframe` — DataFrame renders as table
- `test_format_output_dict` — Dict renders as JSON

## E2E Test Plan (test_full_e2e.py)

### CLI Subprocess Tests
- `test_cli_help` — `--help` returns usage info
- `test_cli_list` — `list` returns functions
- `test_cli_search` — `search 历史行情` returns results
- `test_cli_info` — `info stock_sse_summary` returns function metadata
- `test_cli_categories` — `categories` returns category list
- `test_cli_call` — `call stock_sse_summary` executes function
- `test_cli_json` — `--json list` returns valid JSON

### Workflow Scenarios

1. **Quick market overview**: `call stock_sse_summary` → prints today's exchange summary
2. **Stock analysis pipeline**: `search 历史行情` → `info stock_zh_a_hist` → `call stock_zh_a_hist symbol=000001`
3. **JSON consumption**: `--json call stock_sse_summary` → parseable output
