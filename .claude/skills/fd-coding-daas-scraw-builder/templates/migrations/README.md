# Migrations

Numbered SQL/schema migrations for the project's store.

## Convention

- One file per migration: `NN_description.sql` (e.g. `001_initial_schema.sql`).
- Migrations apply in order; never edit an already-applied migration.
- Record applied migrations in a `schema_migrations` table.
