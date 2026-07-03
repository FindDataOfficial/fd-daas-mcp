## ADDED Requirements

### Requirement: Multi-level datasource search
The system SHALL expose a `search_datasources` tool that filters datasources across levels — by category (with optional subtree inclusion), by source, by form, and by section — with every filter optional, plus a free-text `query` across source label/description, form label, and section name/instruction.

#### Scenario: Filter by category with subtree
- **WHEN** `search_datasources(category_id=1, include_subtree=true)` is called
- **THEN** the system returns all datasources assigned to category 1 or any of its descendant categories

#### Scenario: Filter by category without subtree
- **WHEN** `search_datasources(category_id=1, include_subtree=false)` is called
- **THEN** the system returns only datasources directly assigned to category 1

#### Scenario: Drill to form level
- **WHEN** `search_datasources(source_name="edgar", form="10-K")` is called
- **THEN** the system returns the edgar datasource annotated with only its `10-K` form and that form's sections

#### Scenario: Drill to section level
- **WHEN** `search_datasources(source_name="edgar", form="10-K", section="Item 7")` is called
- **THEN** the system returns the edgar datasource annotated with only the `10-K` form and the matching section(s)

#### Scenario: Free-text query across levels
- **WHEN** `search_datasources(query="MD&A")` is called
- **THEN** the system returns any datasource whose label/description, any form label, or any section name/instruction matches "MD&A", with the matching form/section highlighted in the result

#### Scenario: No filters returns all datasources
- **WHEN** `search_datasources()` is called with no arguments
- **THEN** the system returns all datasources (no forms/sections expanded, for brevity)

### Requirement: Search result shape reflects drill level
The `search_datasources` result SHALL expand forms and sections only when a form/section filter or free-text query makes them relevant; a plain category/source list returns datasources without expanding their form trees.

#### Scenario: Category-only search is compact
- **WHEN** `search_datasources(category_id=1)` is called with no form/section/query
- **THEN** each returned datasource includes its name, label, category, and `form_count`, but not the full form/section tree

#### Scenario: Section-level search expands the tree
- **WHEN** `search_datasources(source_name="edgar", section="Item 7")` is called
- **THEN** the returned datasource includes the matching form(s) and their matching section(s) with `instruction`

### Requirement: Category subtree is cycle-safe
Subtree expansion SHALL be guarded against cycles (defensive against malformed `parent_id` chains) by tracking visited nodes and capping traversal depth.

#### Scenario: Malformed cycle does not hang
- **WHEN** a category tree contains an accidental `parent_id` cycle and `search_datasources(category_id=X, include_subtree=true)` is called
- **THEN** the traversal terminates (visited-set + depth cap) and returns the reachable non-cyclic descendants without error or infinite loop
