## ADDED Requirements

### Requirement: Edit collection metadata

The system SHALL expose an `update_collection` tool that partially updates an existing collection's `name` and/or `description` in a single call. The caller SHALL provide at least one of `new_name` or `description`; any field that is omitted SHALL be left unchanged. When `new_name` is provided and differs from the collection's current name, the system SHALL enforce that the new name is not already used by another collection. The update SHALL preserve all `datasource_collection_items` rows for the collection (they reference by `collection_id`, not by name). The system SHALL raise a "collection not found" error when the target collection does not exist.

#### Scenario: Update description only
- **WHEN** `update_collection(name="us-disclosure", description="Updated description")` is called and `us-disclosure` exists
- **THEN** the collection's `description` is updated, its `name` is unchanged, and its items remain intact

#### Scenario: Update name only
- **WHEN** `update_collection(name="us-disclosure", new_name="us-securities")` is called and no other collection uses `us-securities`
- **THEN** the collection's `name` is updated, `description` is unchanged, and its items remain intact

#### Scenario: Update both name and description in one call
- **WHEN** `update_collection(name="us-disclosure", new_name="us-securities", description="US securities sources")` is called and `us-securities` is free
- **THEN** both fields are updated in a single call and the collection's items remain intact

#### Scenario: Name collision on update
- **WHEN** `update_collection(name="us-disclosure", new_name="japan-disclosure")` is called and a `japan-disclosure` collection already exists
- **THEN** the system returns an error and does not change either field

#### Scenario: Collection not found
- **WHEN** `update_collection(name="nope", description="x")` is called and `nope` does not exist
- **THEN** the system returns a "collection not found" error

#### Scenario: No fields provided
- **WHEN** `update_collection(name="us-disclosure")` is called with neither `new_name` nor `description`
- **THEN** the system returns an error indicating at least one field to update is required

#### Scenario: Rename to the same name is a no-op for the name field
- **WHEN** `update_collection(name="us-disclosure", new_name="us-disclosure", description="new")` is called
- **THEN** the uniqueness check is skipped (name unchanged), the description is updated, and the call succeeds
