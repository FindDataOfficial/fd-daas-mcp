# datasource-management

## MODIFIED Requirements

### Requirement: Create datasource

The system SHALL expose a `create_datasource` tool that inserts a new row into `sources` with a unique name, label, optional description/url/config, an optional `category_id`, and an optional `score` (numeric, default NULL — no default score set). The created row (including `id` and `score`) SHALL be returned.

#### Scenario: Create a datasource with a category

- **WHEN** `create_datasource(name="edgar", label="SEC EDGAR", category_id=3)` is called
- **THEN** a new `DaasSource` row is created with `name="edgar"`, `label="SEC EDGAR"`, `category_id=3`, `enabled=true`, `score=NULL`, and the created row (including `id`) is returned

#### Scenario: Create a datasource without a category

- **WHEN** `create_datasource(name="edinet", label="Japan EDINET")` is called with no `category_id`
- **THEN** the datasource is created with `category_id = NULL`

#### Scenario: Create a datasource with a score

- **WHEN** `create_datasource(name="edgar", label="SEC EDGAR", score=0.9)` is called
- **THEN** the new row has `score = 0.9` and the returned dict includes `"score": 0.9`

#### Scenario: Duplicate name rejected

- **WHEN** `create_datasource(name="edgar", ...)` is called and a source named "edgar" already exists
- **THEN** the system returns an error and does not create a duplicate

#### Scenario: Nonexistent category rejected

- **WHEN** `create_datasource(..., category_id=999)` references a `category_id` that does not exist
- **THEN** the system returns an error indicating the category was not found

### Requirement: Update datasource

The system SHALL expose an `update_datasource` tool that modifies mutable fields (`label`, `description`, `url`, `config`, `enabled`, `category_id`, `score`) of an existing datasource, identified by `name` or `id`. Passing `clear_score=true` SHALL set `score` back to NULL. Only supplied fields are changed; omitted fields are left unchanged.

#### Scenario: Update label and category

- **WHEN** `update_datasource(name="edgar", label="SEC EDGAR Filings", category_id=5)` is called
- **THEN** the datasource's `label` and `category_id` are updated and the updated row is returned

#### Scenario: Move datasource to a different category

- **WHEN** `update_datasource(name="edgar", category_id=7)` is called
- **THEN** only `category_id` changes; other fields are unchanged

#### Scenario: Clear category

- **WHEN** `update_datasource(name="edgar", category_id=null)` is called
- **THEN** the datasource's `category_id` is set to NULL

#### Scenario: Update the default score

- **WHEN** `update_datasource(name="edgar", score=0.85)` is called
- **THEN** the datasource's `score` is set to `0.85` and the updated row (including `"score": 0.85`) is returned

#### Scenario: Clear the default score

- **WHEN** `update_datasource(name="edgar", clear_score=true)` is called
- **THEN** the datasource's `score` is set to NULL and the updated row reports `"score": null`

#### Scenario: Datasource not found

- **WHEN** `update_datasource(name="nope")` references a nonexistent datasource
- **THEN** the system returns an error indicating the datasource was not found
