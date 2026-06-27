# Feature Specification: MCP Dashboard

**Feature**: 004-dashboard | **Date**: 2025-06-25 | **Status**: Planned

## Overview

A web-based dashboard to manage the cli-anything MCP ecosystem's databases. Provides read-only browsing of all SQLite databases, CRUD management for cron tasks/schedules, datasource metadata management, and a skill to scaffold new ECharts-powered visualization pages.

## User Stories

### US1: Database Viewer (P1)

As a developer, I want to see all MCP databases and browse their tables, so I can inspect the data without running raw SQL.

**Acceptance**:
- List all registered SQLite databases with table counts
- Click a table to see paginated rows (50 per page)
- Sort by any column
- Read-only — no accidental modifications

### US2: Cron Task Management (P1)

As a developer, I want to edit cron tasks and toggle schedules from a web UI, so I don't need to use MCP tools for routine changes.

**Acceptance**:
- View all tasks with their linked schedules
- Edit task command, description, timeout
- Toggle schedule enabled/disabled
- Delete tasks (with confirmation)
- ECharts bar chart showing execution history (success/fail per day)

### US3: Datasource & Column Management (P2)

As a developer, I want to register datasources and document their columns, so I have a catalog of available data.

**Acceptance**:
- Add datasource (name, type, connection string, description)
- Auto-scan SQLite table schemas to populate columns
- Edit column descriptions and types
- Delete datasources

### US4: Dashboard Page Skill (P2)

As a developer, I want to type `/dashboard-page` and have Claude scaffold a new ECharts page, so I can visualize any query without manual coding.

**Acceptance**:
- Skill prompts for page name, SQL query, chart type
- Generates Flask route + Jinja2 template + ECharts config
- Registers route in app.py
- Page renders immediately at the new URL

## Non-Functional Requirements

- **Performance**: Page load < 1s for tables with < 1000 rows
- **Security**: Local-only (bind to 127.0.0.1). No auth for v1.
- **Compatibility**: Python 3.10+, modern browsers (Chrome, Firefox, Safari)
- **Extensibility**: Dashboard page skill makes adding new pages trivial

## Out of Scope (v1)

- User authentication/authorization
- Write operations on leader_mcp.db
- Real-time updates (WebSocket/polling)
- Docker deployment
- Mobile responsive design
