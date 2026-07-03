## ADDED Requirements

### Requirement: Datasource exposes forms
The system SHALL maintain a `datasource_forms` table where each row belongs to one `DaasSource` (FK with `ON DELETE CASCADE`) and carries a `form_type` (e.g. `10-K`, `8-K`, `20-F`) and an optional `label`.

#### Scenario: A source has multiple forms
- **WHEN** a datasource represents EDGAR
- **THEN** it can have separate `datasource_forms` rows for `10-K`, `10-Q`, and `8-K`

### Requirement: Add form to datasource
The system SHALL expose an `add_form` tool that creates a `datasource_forms` row under a given datasource.

#### Scenario: Add a form
- **WHEN** `add_form(source_name="edgar", form_type="10-K", label="Annual Report")` is called
- **THEN** a `datasource_forms` row is created FK-linked to the edgar source and returned

#### Scenario: Datasource not found
- **WHEN** `add_form(source_name="nope", form_type="10-K")` references a nonexistent datasource
- **THEN** the system returns an error indicating the datasource was not found

### Requirement: Form has sections with instructions
The system SHALL maintain a `datasource_sections` table where each row belongs to one form (FK with `ON DELETE CASCADE`), carries a `section_name` (e.g. `Item 1 Business`, `Item 7 MD&A`), and an `instruction` (free-text extraction prompt/rule).

#### Scenario: A form has multiple sections
- **WHEN** the `10-K` form is configured
- **THEN** it can have separate `datasource_sections` rows for `Item 1 Business` and `Item 7 MD&A`, each with its own `instruction`

### Requirement: Add section to form
The system SHALL expose an `add_section` tool that creates a `datasource_sections` row under a given form, carrying the section name and instruction.

#### Scenario: Add a section with an instruction
- **WHEN** `add_section(form_id=2, section_name="Item 1 Business", instruction="Extract the company-description paragraph.")` is called
- **THEN** a `datasource_sections` row is created FK-linked to form 2 and returned

#### Scenario: Add a section without an instruction
- **WHEN** `add_section(form_id=2, section_name="Item 1A Risk Factors")` is called with no instruction
- **THEN** the section is created with `instruction = NULL`

#### Scenario: Form not found
- **WHEN** `add_section(form_id=999, section_name="...")` references a nonexistent form
- **THEN** the system returns an error indicating the form was not found

### Requirement: List forms and sections for a datasource
The system SHALL expose a `list_forms` tool that returns all forms of a datasource, each with its nested sections (including `instruction`).

#### Scenario: List forms with sections
- **WHEN** `list_forms(source_name="edgar")` is called
- **THEN** the system returns each form with its `form_type`, `label`, and a nested list of sections (each with `section_name` and `instruction`)

#### Scenario: Datasource with no forms
- **WHEN** `list_forms(source_name="worldbank")` is called on a source with no configured forms
- **THEN** the system returns an empty forms list (not an error)
