## ADDED Requirements

### Requirement: CNINFO category catalog is a data-driven JSON registry

The system SHALL ship a JSON registry file (`mcp/cnreport-mcp/cninfo_categories.json`) as the single source of truth for CNINFO disclosure category codes. The registry SHALL group categories by disclosure type (e.g. 定期报告, 融资, 业绩, 股权变动, 公司治理, 担保, 其他), and each entry SHALL carry a Chinese `name`, a CNINFO `code` (e.g. `category_ndbg_szsh`), and a short `description`. `cninfo_client.py` SHALL load this registry once at module import and expose a `load_categories()` accessor returning the cached structure. The previously hardcoded `_FORM_CATEGORIES` dict SHALL be replaced by lookups against this registry.

#### Scenario: Registry covers the four periodic forms

- **WHEN** the registry is loaded
- **THEN** it contains entries mapping `年度报告` → `category_ndbg_szsh`, `半年度报告` → `category_bndbg_szsh`, `第一季度报告` → `category_yjdbg_szsh`, and `第三季度报告` → `category_sjdbg_szsh`, so existing `form`-based calls resolve unchanged

#### Scenario: Registry is grouped

- **WHEN** the registry is loaded
- **THEN** each category belongs to a named group, and the four periodic forms belong to the `定期报告` group

#### Scenario: Registry load failure is surfaced clearly

- **WHEN** the registry file is missing or malformed at server boot
- **THEN** `load_categories()` raises a clear error naming the missing file, rather than silently degrading to an empty catalog

### Requirement: list_report_types returns the catalog

The system SHALL expose a `list_report_types(group: Optional[str] = None)` MCP tool that returns the CNINFO disclosure category catalog. With no `group` argument it SHALL return every group with its categories; with a `group` argument it SHALL return only the categories in that group. Each returned category SHALL include `name`, `code`, and `description`. The result SHALL include a `count` of categories returned.

#### Scenario: List all report types

- **WHEN** `list_report_types()` is called with no arguments
- **THEN** it returns a `groups` array where each group has a `name` and a `categories` array, and the response includes the total category `count`

#### Scenario: Filter by group

- **WHEN** `list_report_types(group="定期报告")` is called
- **THEN** it returns only the categories in the `定期报告` group (年度报告, 半年度报告, 第一季度报告, 第三季度报告), each with its `code`

#### Scenario: Unknown group returns an error

- **WHEN** `list_report_types(group="不存在的组")` is called
- **THEN** it returns an `error` field indicating the group was not found, without raising

### Requirement: Catalog is extensible without code changes

Adding a CNINFO report type SHALL require only an edit to `cninfo_categories.json` — no change to `cninfo_client.py`, `cnreport_tools.py`, or `server.py`. After a server restart, a newly added category SHALL appear in `list_report_types` output and SHALL be accepted by `list_filings(category=…)` and `get_special_report(category=…)`.

#### Scenario: Newly added category is discoverable and addressable

- **WHEN** a new entry `{name: "测试报告", code: "category_test_szsh"}` is appended to a group in `cninfo_categories.json` and the server is restarted
- **THEN** `list_report_types()` includes "测试报告", and `list_filings(ticker_or_name="600519", category="测试报告")` resolves it to `category_test_szsh` and sends that code to CNINFO (rather than returning an unknown-category error)

### Requirement: list_report_types never raises

The `list_report_types` tool SHALL catch exceptions from registry loading and return a dict with an `error` string field instead of raising, matching the error convention of the other cnreport-mcp tools.

#### Scenario: Registry read failure surfaces as an error field

- **WHEN** the registry cannot be read and `list_report_types` is called
- **THEN** the tool returns `{"error": "<message>"}` and the MCP server remains healthy
