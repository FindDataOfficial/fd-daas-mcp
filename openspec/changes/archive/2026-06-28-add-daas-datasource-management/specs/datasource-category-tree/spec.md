## ADDED Requirements

### Requirement: Category table is hierarchical
The system SHALL maintain a `categories` table with a self-referencing `parent_id` (nullable for roots), `name`, `label`, and `sort_order`, so categories form a tree.

#### Scenario: Root category
- **WHEN** a category is created with no `parent_id`
- **THEN** it is a root category (top of its tree)

#### Scenario: Child category
- **WHEN** a category is created with a `parent_id` pointing to an existing category
- **THEN** it is a child of that category in the tree

### Requirement: Create category
The system SHALL expose a `create_category` tool that inserts a new category, optionally under a parent.

#### Scenario: Create a root category
- **WHEN** `create_category(name="finance", label="Finance")` is called
- **THEN** a root category is created with `parent_id = NULL` and returned

#### Scenario: Create a child category
- **WHEN** `create_category(name="us-disclosure", label="US Disclosure", parent_id=1)` is called
- **THEN** the category is created with `parent_id = 1`

#### Scenario: Parent not found
- **WHEN** `create_category(..., parent_id=999)` references a nonexistent parent
- **THEN** the system returns an error indicating the parent category was not found

### Requirement: Move category
The system SHALL expose a `move_category` tool that re-parents a category, rejecting moves that would create a cycle.

#### Scenario: Move category under a new parent
- **WHEN** `move_category(category_id=3, parent_id=1)` is called
- **THEN** the category's `parent_id` is updated to 1

#### Scenario: Reject cycle — move into own descendant
- **WHEN** `move_category(category_id=1, parent_id=3)` is called and category 3 is a descendant of category 1
- **THEN** the system returns an error and does not change `parent_id`

#### Scenario: Reject self-parenting
- **WHEN** `move_category(category_id=3, parent_id=3)` is called
- **THEN** the system returns an error indicating a category cannot be its own parent

### Requirement: Delete category
The system SHALL expose a `delete_category` tool. Deleting a category with children SHALL be rejected unless a re-parent strategy is supplied, to prevent orphaning.

#### Scenario: Delete a leaf category
- **WHEN** `delete_category(category_id=5)` is called on a category with no children and no datasources assigned
- **THEN** the category is removed

#### Scenario: Reject delete of category with children
- **WHEN** `delete_category(category_id=1)` is called on a category that has child categories
- **THEN** the system returns an error indicating the category has children and cannot be deleted

#### Scenario: Delete category with assigned datasources
- **WHEN** `delete_category(category_id=3)` is called on a category with datasources assigned to it
- **THEN** those datasources have their `category_id` set to NULL (orphaned to root level) and the category is removed

### Requirement: Get category tree
The system SHALL expose a `get_category_tree` tool that returns the full category tree (or a subtree from a given root) as a nested structure, including the count of datasources in each category.

#### Scenario: Full tree
- **WHEN** `get_category_tree()` is called with no arguments
- **THEN** the system returns all root categories with their nested children, each annotated with `datasource_count`

#### Scenario: Subtree
- **WHEN** `get_category_tree(root_id=1)` is called
- **THEN** the system returns category 1 and its full descendant subtree
