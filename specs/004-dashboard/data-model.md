# Data Model: MCP Dashboard

**Feature**: 004-dashboard | **Date**: 2025-06-25

## Existing Databases (Read-Only from Dashboard)

### leader_mcp.db

These tables exist and are read-only from the dashboard:

#### `functions`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| harness | VARCHAR | Source harness name (e.g., "akshare") |
| command | VARCHAR | Function/command name |
| category | VARCHAR | Category tag |
| source | VARCHAR | Source identifier |
| description | TEXT | Human-readable description |
| parameters | JSON | Parameter definitions array |
| created_at | DATETIME | Creation timestamp |
| updated_at | DATETIME | Last update timestamp |

#### `function_columns`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| function_id | INTEGER FK | References functions.id |
| column_name | VARCHAR | Output column name |
| column_type | VARCHAR | Data type (str, int, float, etc.) |
| column_description | TEXT | Column description |
| created_at | DATETIME | Creation timestamp |

#### `harnesses`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| name | VARCHAR UNIQUE | Harness name |
| description | TEXT | Harness description |
| created_at | DATETIME | Creation timestamp |

#### `categories`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| name | VARCHAR UNIQUE | Category name |
| harness_id | INTEGER FK | References harnesses.id |
| created_at | DATETIME | Creation timestamp |

### cron.db

These tables exist and are **read-write** (managed via cron-mcp's existing API):

#### `tasks`
| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR PK | Task name (string ID) |
| command | VARCHAR | Shell command or script path |
| description | TEXT | Task description |
| timeout | INTEGER | Timeout in seconds (default 60) |
| created_at | DATETIME | Creation timestamp |
| updated_at | DATETIME | Last update timestamp |

#### `schedules`
| Column | Type | Description |
|--------|------|-------------|
| id | VARCHAR PK | UUID string |
| name | VARCHAR | Schedule name |
| cron | VARCHAR | Cron expression |
| task_id | VARCHAR FK | References tasks.id |
| enabled | BOOLEAN | Whether schedule is active |
| timezone | VARCHAR | Timezone (default "UTC") |
| agent | VARCHAR | Agent name (nullable) |
| prompt | TEXT | Agent prompt (nullable) |
| created_at | DATETIME | Creation timestamp |
| updated_at | DATETIME | Last update timestamp |

#### `executions`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| schedule_id | VARCHAR FK | References schedules.id |
| status | VARCHAR | Execution status |
| started_at | DATETIME | Start time |
| finished_at | DATETIME | End time (nullable) |
| output | TEXT | Execution output (nullable) |
| error | TEXT | Error message (nullable) |

## New Database: dashboard.db

Created and managed by the dashboard app:

### `datasources`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| name | VARCHAR(255) UNIQUE NOT NULL | Datasource name |
| db_type | VARCHAR(50) NOT NULL | "sqlite" (extensible: "postgresql", "mysql") |
| connection_string | VARCHAR(500) NOT NULL | File path or connection URI |
| description | TEXT | Human-readable description |
| is_readonly | BOOLEAN DEFAULT TRUE | Whether dashboard treats it as read-only |
| created_at | DATETIME DEFAULT NOW | Creation timestamp |
| updated_at | DATETIME DEFAULT NOW | Last update timestamp |

### `datasource_columns`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| datasource_id | INTEGER FK NOT NULL | References datasources.id |
| table_name | VARCHAR(255) NOT NULL | Which table this column belongs to |
| column_name | VARCHAR(255) NOT NULL | Column name |
| column_type | VARCHAR(50) | Data type |
| is_primary_key | BOOLEAN DEFAULT FALSE | Whether it's a PK |
| is_nullable | BOOLEAN DEFAULT TRUE | Whether nullable |
| description | TEXT | Column description |
| created_at | DATETIME DEFAULT NOW | Creation timestamp |

**Unique constraint**: (datasource_id, table_name, column_name)

## Entity Relationships

```
leader_mcp.db                          cron.db
─────────────                          ───────
harnesses ──< categories              tasks ──< schedules ──< executions
functions ──< function_columns

dashboard.db
────────────
datasources ──< datasource_columns
```

Dashboard reads leader_mcp.db directly. Dashboard reads/writes cron.db (preferring cron-mcp API). Dashboard owns dashboard.db.

## State Transitions

### Schedule Lifecycle
```
[created] → enabled=true → [active] → (cron triggers) → [executing] → [completed|failed]
                ↓                        ↑
           enabled=false → [paused] → enabled=true
```

### Execution States
```
[pending] → [running] → [completed|failed|timeout]
```
