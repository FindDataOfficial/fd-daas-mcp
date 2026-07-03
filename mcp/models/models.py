"""Single source of truth for all database schemas across the MCP ecosystem.

Every MCP server and the dashboard share this one Base. Schema changes
MUST be made here first, then reflected in consuming code.

34 tables across all MCP domains (adds Entity + EntityDatasourceLink for the
entity→datasource coverage layer; +LeaderUpstream for the leader-mcp data
gateway; +PipelineCollection + PipelineCollectionItem for daas-mcp managed
fetch+cron collections).

Domains:
  leader-mcp:  Function, FunctionColumn, DataSnapshot (harness-based registry)
  cron-mcp:    Schedule, Execution, Task (scheduler data)
  daas-mcp:    DaasSource, DaasFunction, DaasFunctionColumn, Observation (source-based registry)
  daas-mcp mgmt: Category, DatasourceForm, DatasourceSection, DatasourceCollection,
                 DatasourceCollectionItem, PipelineCollection, PipelineCollectionItem
  scrapling:   ScrawConfig (scraping configs)
  dashboard:   Datasource, DatasourceColumn (dashboard metadata)
  process-mcp: ProcessRule, ProcessResult (LLM extraction rules + results)
  entity:      Entity, EntityDatasourceLink (stocks + countries, linked to daas sources)
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# ═══════════════════════════════════════════════════════════════
# leader-mcp domain — harness-based registry
# ═══════════════════════════════════════════════════════════════


class Function(Base):
    __tablename__ = "functions"
    __table_args__ = (UniqueConstraint("harness", "command", name="uq_harness_command"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    harness = Column(String(64), nullable=False, index=True)
    command = Column(String(255), nullable=False, index=True)
    category = Column(String(255), nullable=False, default="未分类")
    source = Column(String(512), nullable=True)
    description = Column(String, nullable=True)
    parameters = Column(JSON, nullable=True)
    is_datasource = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    last_fetched_at = Column(DateTime, nullable=True)

    columns = relationship(
        "FunctionColumn", back_populates="function", cascade="all, delete-orphan", lazy="selectin"
    )

    def to_dict(self) -> dict:
        return {
            "harness": self.harness,
            "command": self.command,
            "category": self.category,
            "source": self.source,
            "description": self.description,
            "parameters": self.parameters or [],
            "is_datasource": self.is_datasource,
            "enabled": self.enabled,
            "last_fetched_at": self.last_fetched_at.isoformat() if self.last_fetched_at else None,
            "columns": [c.to_dict() for c in self.columns] if self.columns else [],
        }


class FunctionColumn(Base):
    __tablename__ = "function_columns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    function_id = Column(
        Integer, ForeignKey("functions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    column_name = Column(String(255), nullable=False)
    column_type = Column(String(64), nullable=True)
    column_description = Column(String, nullable=True)
    source_field = Column(String(255), nullable=True)
    unit = Column(String(32), nullable=True)
    semantic_type = Column(String(64), nullable=True)

    function = relationship("Function", back_populates="columns")

    def to_dict(self) -> dict:
        return {
            "name": self.column_name,
            "type": self.column_type,
            "description": self.column_description,
            "source_field": self.source_field,
            "unit": self.unit,
            "semantic_type": self.semantic_type,
        }


class DataSnapshot(Base):
    __tablename__ = "data_snapshots"
    __table_args__ = (UniqueConstraint("function_id", "params_json", name="uq_snapshot_function_params"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    function_id = Column(
        Integer, ForeignKey("functions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    params_json = Column(JSON, nullable=False)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(16), default="success")
    data_json = Column(JSON, nullable=True)
    row_count = Column(Integer, default=0)

    function = relationship("Function")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "function_id": self.function_id,
            "params_json": self.params_json,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "status": self.status,
            "row_count": self.row_count,
        }


class LeaderUpstream(Base):
    """A data-fetch MCP upstream that leader-mcp launches on demand as a stdio
    subprocess and calls via a fastmcp.Client. Replaces the direct `.mcp.json`
    connection for the project's data-fetch MCPs (yfinance, edgartools, …).

    transport is 'stdio' (command + args_json + cwd + env_json). The
    fastmcp.Client is built per call from these fields (see gateway_database.
    build_client), mirroring combine-mcp's Upstream pattern — but scoped
    globally (one row per data-fetch MCP), not per-composite.
    """
    __tablename__ = "leader_upstreams"
    __table_args__ = (UniqueConstraint("name", name="uq_leader_upstream_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, index=True)
    transport = Column(String(16), nullable=False, default="stdio")
    command = Column(String, nullable=True)        # stdio executable
    args_json = Column(JSON, nullable=True)        # stdio argv list
    env_json = Column(JSON, nullable=True)         # stdio env dict (optional override)
    cwd = Column(String, nullable=True)            # stdio working directory
    enabled = Column(Boolean, default=True, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "transport": self.transport,
            "command": self.command,
            "args": self.args_json or [],
            "env": self.env_json or {},
            "cwd": self.cwd,
            "enabled": bool(self.enabled),
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ═══════════════════════════════════════════════════════════════
# cron-mcp domain — scheduler data
# ═══════════════════════════════════════════════════════════════


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(String, primary_key=True, default=lambda: _short_uuid())
    name = Column(String, nullable=False)
    cron_expr = Column(String, nullable=False)
    task_name = Column(String, nullable=False)
    agent = Column(String, nullable=True)
    prompt = Column(Text, nullable=True)
    enabled = Column(Integer, default=1)
    timezone = Column(String, default="UTC")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)


class Execution(Base):
    __tablename__ = "executions"

    id = Column(String, primary_key=True, default=lambda: _short_uuid())
    schedule_id = Column(String, nullable=False, index=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending")
    output = Column(Text, nullable=True)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: _short_uuid())
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    command = Column(Text, nullable=False)
    timeout = Column(Integer, default=60)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ═══════════════════════════════════════════════════════════════
# daas-mcp domain — source-based registry
# ═══════════════════════════════════════════════════════════════


class DaasSource(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, index=True)
    label = Column(String(128), nullable=False)
    description = Column(String, nullable=True)
    url = Column(String(512), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    config = Column(JSON, nullable=True)
    category_id = Column(
        Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    functions = relationship(
        "DaasFunction", back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )
    forms = relationship(
        "DatasourceForm", back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )
    category = relationship("Category", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "url": self.url,
            "enabled": self.enabled,
            "config": self.config or {},
            "category_id": self.category_id,
            "function_count": len(self.functions) if self.functions else 0,
        }


class DaasFunction(Base):
    __tablename__ = "daas_functions"
    __table_args__ = (UniqueConstraint("source_id", "name", name="uq_source_daas_function"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False, index=True)
    label = Column(String(255), nullable=True)
    description = Column(String, nullable=True)
    category = Column(String(255), nullable=False, default="未分类")
    parameters = Column(JSON, nullable=True)
    output_type = Column(String(64), default="DataFrame")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    source = relationship("DaasSource", back_populates="functions")
    columns = relationship(
        "DaasFunctionColumn",
        back_populates="function",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self) -> dict:
        return {
            "source": self.source.name if self.source else None,
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "category": self.category,
            "parameters": self.parameters or [],
            "output_type": self.output_type,
            "columns": [c.to_dict() for c in self.columns] if self.columns else [],
        }


class DaasFunctionColumn(Base):
    __tablename__ = "daas_function_columns"
    __table_args__ = (UniqueConstraint("function_id", "name", name="uq_daas_function_column"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    function_id = Column(
        Integer, ForeignKey("daas_functions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    label = Column(String(255), nullable=True)
    type = Column(String(64), nullable=True)
    description = Column(String, nullable=True)
    nullable = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    function = relationship("DaasFunction", back_populates="columns")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "description": self.description,
            "nullable": self.nullable,
        }


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("source", "function_name", "indicator", "date", name="uq_observation"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(64), nullable=False, index=True)
    function_name = Column(String(255), nullable=False, index=True)
    indicator = Column(String(255), nullable=False, index=True)
    date = Column(String(64), nullable=False, index=True)
    value = Column(String(64), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "function_name": self.function_name,
            "indicator": self.indicator,
            "date": self.date,
            "value": self.value,
            "metadata": self.metadata_ or {},
        }


# ═══════════════════════════════════════════════════════════════
# daas-mcp management domain — categories, forms, sections, collections
# (additive to the source-based registry above)
# ═══════════════════════════════════════════════════════════════


class Category(Base):
    """Hierarchical category tree for datasources. Self-referencing parent_id."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True, index=True)
    label = Column(String(255), nullable=True)
    parent_id = Column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True, index=True
    )
    sort_order = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    children = relationship(
        "Category",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    parent = relationship(
        "Category", back_populates="children", remote_side=[id], lazy="selectin"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "parent_id": self.parent_id,
            "sort_order": self.sort_order,
        }


class DatasourceForm(Base):
    """A form exposed by a datasource (e.g. EDGAR '10-K', '8-K')."""
    __tablename__ = "datasource_forms"
    __table_args__ = (UniqueConstraint("source_id", "form_type", name="uq_source_form_type"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    form_type = Column(String(64), nullable=False)
    label = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    source = relationship("DaasSource", back_populates="forms")
    sections = relationship(
        "DatasourceSection",
        back_populates="form",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "form_type": self.form_type,
            "label": self.label,
            "sections": [s.to_dict() for s in self.sections] if self.sections else [],
        }


class DatasourceSection(Base):
    """A section of a form, carrying an extraction instruction.

    e.g. form '10-K' → section 'Item 1 Business' → instruction 'Extract the
    company-description paragraph.'
    """
    __tablename__ = "datasource_sections"
    __table_args__ = (UniqueConstraint("form_id", "section_name", name="uq_form_section_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    form_id = Column(
        Integer, ForeignKey("datasource_forms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_name = Column(String(255), nullable=False)
    instruction = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    form = relationship("DatasourceForm", back_populates="sections")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "form_id": self.form_id,
            "section_name": self.section_name,
            "instruction": self.instruction,
            "sort_order": self.sort_order,
        }


class DatasourceCollection(Base):
    """A named collection of datasources (or specific datasource-sections)."""
    __tablename__ = "datasource_collections"
    __table_args__ = (UniqueConstraint("name", name="uq_datasource_collection_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    items = relationship(
        "DatasourceCollectionItem",
        back_populates="collection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "item_count": len(self.items) if self.items else 0,
        }


class DatasourceCollectionItem(Base):
    """One entry in a collection: a whole datasource (section_id NULL) or a
    specific datasource-section (section_id set)."""
    __tablename__ = "datasource_collection_items"
    __table_args__ = (
        UniqueConstraint("collection_id", "source_id", "section_id", name="uq_collection_item"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(
        Integer, ForeignKey("datasource_collections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id = Column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id = Column(
        Integer, ForeignKey("datasource_sections.id", ondelete="CASCADE"), nullable=True, index=True
    )
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    collection = relationship("DatasourceCollection", back_populates="items")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "source_id": self.source_id,
            "section_id": self.section_id,
            "sort_order": self.sort_order,
        }


class PipelineCollection(Base):
    """A named collection of fetch *items* — a managed "datasource collection"
    where each item binds a source MCP (`source_mcp` + `tool` + `arguments_json`)
    to a `scraw_<slug>` storage target and a cron cadence. Distinct from the
    curation-only `DatasourceCollection` (which groups datasources for the
    NotebookLM-style workspace and carries no fetch/storage/cron semantics).

    Adding an enabled item triggers an immediate history backfill + a
    `cron-mcp` schedule; removing/disabling an item unwires the schedule.
    """
    __tablename__ = "pipeline_collections"
    __table_args__ = (UniqueConstraint("name", name="uq_pipeline_collection_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    items = relationship(
        "PipelineCollectionItem",
        back_populates="collection",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "item_count": len(self.items) if self.items else 0,
        }


class PipelineCollectionItem(Base):
    """One fetch unit in a `PipelineCollection`.

    `source_mcp` is a server name in `.mcp.json` (e.g. `akshare-mcp`); `tool`
    is the tool to call on that MCP (e.g. `call_akshare_function`); the tool's
    kwargs live in `arguments_json` (e.g. `{"name":"stock_zh_a_hist",
    "params_json":"{\\"symbol\\":\\"000001\\"}"}`). This is the `data_job`
    shape from `add-cron-mcp-data-fetch`, so items migrate 1:1 to
    `create_data_job` later.

    `task_name` is the `cron-mcp` task name (`pipeline_<collection>_<item>`),
    stored so remove/disable can delete the right rows. `last_run_at` /
    `last_status` / `last_row_count` / `error_message` record the most recent
    backfill or cron tick.
    """
    __tablename__ = "pipeline_collection_items"
    __table_args__ = (
        UniqueConstraint("collection_id", "name", name="uq_pipeline_collection_item"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(
        Integer,
        ForeignKey("pipeline_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(128), nullable=False)
    source_mcp = Column(String(128), nullable=False)
    tool = Column(String(255), nullable=False)
    arguments_json = Column(Text, nullable=True)
    storage_table = Column(String(128), nullable=False)
    upsert_keys_json = Column(Text, nullable=True)
    cron_expr = Column(String(64), nullable=False)
    timezone = Column(String(64), nullable=False, default="Asia/Shanghai")
    enabled = Column(Boolean, default=True, nullable=False)
    task_name = Column(String(255), nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    last_status = Column(String(32), nullable=True)  # ok | backfill_failed | cron_failed | backfill_timeout
    last_row_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    collection = relationship("PipelineCollection", back_populates="items")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "name": self.name,
            "source_mcp": self.source_mcp,
            "tool": self.tool,
            "arguments": _json_loads(self.arguments_json),
            "storage_table": self.storage_table,
            "upsert_keys": _json_loads(self.upsert_keys_json),
            "cron_expr": self.cron_expr,
            "timezone": self.timezone,
            "enabled": bool(self.enabled),
            "task_name": self.task_name,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_status": self.last_status,
            "last_row_count": self.last_row_count,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def _json_loads(raw):
    import json as _json
    if raw is None:
        return None
    try:
        return _json.loads(raw)
    except (ValueError, TypeError):
        return raw


# ═══════════════════════════════════════════════════════════════
# scrapling-mcp domain
# ═══════════════════════════════════════════════════════════════


class ScrawConfig(Base):
    __tablename__ = "scraw_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), nullable=False)
    name = Column(String(255), nullable=False)
    columns_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════════════════
# settings domain — centralized env configuration
# ═══════════════════════════════════════════════════════════════


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("scope", "key", name="uq_setting_scope_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(64), nullable=False, index=True, default="global")
    key = Column(String(128), nullable=False)
    value = Column(Text, nullable=False, default="")
    category = Column(String(16), nullable=False, default="runtime")  # 'bootstrap' | 'runtime'
    description = Column(String, nullable=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ═══════════════════════════════════════════════════════════════
# dashboard domain
# ═══════════════════════════════════════════════════════════════


class Datasource(Base):
    __tablename__ = "datasources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    db_type = Column(String, nullable=False, default="sqlite")
    connection_string = Column(String, nullable=False)
    description = Column(String, default="")
    is_readonly = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DatasourceColumn(Base):
    __tablename__ = "datasource_columns"
    __table_args__ = (UniqueConstraint("datasource_id", "table_name", "column_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    datasource_id = Column(
        Integer, ForeignKey("datasources.id", ondelete="CASCADE"), nullable=False
    )
    table_name = Column(String, nullable=False)
    column_name = Column(String, nullable=False)
    column_type = Column(String, default="")
    is_primary_key = Column(Integer, default=0)
    is_nullable = Column(Integer, default=1)
    description = Column(String, default="")
    source_field = Column(String, default="")
    unit = Column(String, default="")
    semantic_type = Column(String, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ═══════════════════════════════════════════════════════════════
# combine-mcp domain — composite MCP curation + orchestration
# ═══════════════════════════════════════════════════════════════


class Composite(Base):
    __tablename__ = "composites"
    __table_args__ = (UniqueConstraint("name", name="uq_composite_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Upstream(Base):
    """One upstream MCP connection, scoped to a composite.

    transport: 'stdio' (command+args) or 'http' (url).
    Scoped per-composite (denormalized) — two composites wanting the same
    upstream each define their own row.
    """
    __tablename__ = "upstreams"
    __table_args__ = (UniqueConstraint("composite_id", "key", name="uq_composite_upstream_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    composite_id = Column(Integer, ForeignKey("composites.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(128), nullable=False)  # short id used as mount namespace
    transport = Column(String(16), nullable=False, default="stdio")  # 'stdio' | 'http'
    command = Column(String, nullable=True)   # stdio: executable
    args = Column(JSON, nullable=True)        # stdio: argv
    env = Column(JSON, nullable=True)         # stdio: env dict
    cwd = Column(String, nullable=True)       # stdio: working directory
    url = Column(String, nullable=True)       # http: upstream URL
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "composite_id": self.composite_id,
            "key": self.key,
            "transport": self.transport,
            "command": self.command,
            "args": self.args or [],
            "env": self.env or {},
            "cwd": self.cwd,
            "url": self.url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CompositeTool(Base):
    """A selected tool from an upstream, exposed (proxied) by a composite."""
    __tablename__ = "composite_tools"
    __table_args__ = (
        UniqueConstraint("composite_id", "upstream_key", "tool_name", name="uq_composite_tool"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    composite_id = Column(Integer, ForeignKey("composites.id", ondelete="CASCADE"), nullable=False, index=True)
    upstream_key = Column(String(128), nullable=False)
    tool_name = Column(String(255), nullable=False)
    alias = Column(String(255), nullable=True)  # retained for forward compat; unused in v1
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "composite_id": self.composite_id,
            "upstream_key": self.upstream_key,
            "tool_name": self.tool_name,
            "alias": self.alias,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CompositeChain(Base):
    """A chained tool: a linear pipeline of upstream tool calls."""
    __tablename__ = "composite_chains"
    __table_args__ = (UniqueConstraint("composite_id", "name", name="uq_composite_chain_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    composite_id = Column(Integer, ForeignKey("composites.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(String, nullable=True)
    steps = Column(JSON, nullable=False)  # [{upstream, tool, input: {...}}]
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "composite_id": self.composite_id,
            "name": self.name,
            "description": self.description,
            "steps": self.steps or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════
# helpers
# ═══════════════════════════════════════════════════════════════


def _short_uuid() -> str:
    import uuid
    return str(uuid.uuid4())[:8]


# ═══════════════════════════════════════════════════════════════
# cnreport-mcp domain — Chinese annual report extraction + ES index
# ═══════════════════════════════════════════════════════════════


class ReportDocument(Base):
    """One fetched annual report. report_id is a stable hash of source+company+year."""
    __tablename__ = "report_documents"
    __table_args__ = (UniqueConstraint("report_id", name="uq_report_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(128), nullable=False, index=True)
    source = Column(String(2048), nullable=False)
    company = Column(String(255), nullable=True, index=True)
    stock_code = Column(String(32), nullable=True, index=True)
    year = Column(Integer, nullable=True, index=True)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    raw_path = Column(String(2048), nullable=True)
    parse_status = Column(String(16), default="ok")  # ok | partial | failed

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "source": self.source,
            "company": self.company,
            "stock_code": self.stock_code,
            "year": self.year,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "raw_path": self.raw_path,
            "parse_status": self.parse_status,
        }


class ReportSection(Base):
    """One outline node extracted from a report. Idempotent on report_id+ordinal."""
    __tablename__ = "report_sections"
    __table_args__ = (
        UniqueConstraint("report_id", "ordinal", name="uq_report_section_ordinal"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(128), nullable=False, index=True)
    ordinal = Column(Integer, nullable=False)
    level = Column(Integer, default=1)
    title = Column(String(512), nullable=False)
    char_count = Column(Integer, default=0)
    parse_status = Column(String(16), default="ok")  # ok | missing | failed
    extracted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "ordinal": self.ordinal,
            "level": self.level,
            "title": self.title,
            "char_count": self.char_count,
            "parse_status": self.parse_status,
        }


class EsIndexMeta(Base):
    """Metadata for a cnreport-{year} Elasticsearch index."""
    __tablename__ = "es_index_meta"
    __table_args__ = (UniqueConstraint("index_name", name="uq_es_index_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    index_name = Column(String(128), nullable=False, index=True)
    doc_count = Column(Integer, default=0)
    mapping_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "index_name": self.index_name,
            "doc_count": self.doc_count,
            "mapping_hash": self.mapping_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ═══════════════════════════════════════════════════════════════
# process-mcp domain — LLM extraction rules + results
# ═══════════════════════════════════════════════════════════════


class ProcessRule(Base):
    """A persisted extraction rule: bind a source-data table + text column to
    a JSON Schema + model, replayable incrementally via run_rule.

    source_table is a dynamically-created scraped-data table (convention:
    `scraw_<slug>`), NOT a registry table. last_rowid is the incremental cursor.
    """
    __tablename__ = "process_rules"
    __table_args__ = (UniqueConstraint("name", name="uq_process_rule_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    source_table = Column(String(128), nullable=False)
    text_column = Column(String(128), nullable=False)
    schema_json = Column(JSON, nullable=False)
    prompt = Column(Text, nullable=True)
    model = Column(String(128), nullable=True)
    max_chars = Column(Integer, nullable=False, default=12000)
    enabled = Column(Boolean, default=True, nullable=False)
    last_rowid = Column(Integer, nullable=False, default=0)
    datasource = Column(String(128), nullable=True)  # traceability only (daas sources.name)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "source_table": self.source_table,
            "text_column": self.text_column,
            "schema": self.schema_json or {},
            "prompt": self.prompt,
            "model": self.model,
            "max_chars": self.max_chars,
            "enabled": self.enabled,
            "last_rowid": self.last_rowid,
            "datasource": self.datasource,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProcessResult(Base):
    """One extraction result row, idempotent on (rule_id, source_table, source_rowid)."""
    __tablename__ = "process_results"
    __table_args__ = (
        UniqueConstraint("rule_id", "source_table", "source_rowid", name="uq_process_result"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(
        Integer, ForeignKey("process_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_table = Column(String(128), nullable=False, index=True)
    source_rowid = Column(Integer, nullable=False, index=True)
    extracted_json = Column(JSON, nullable=True)
    model = Column(String(128), nullable=True)
    run_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "source_table": self.source_table,
            "source_rowid": self.source_rowid,
            "extracted": self.extracted_json,
            "model": self.model,
            "run_at": self.run_at.isoformat() if self.run_at else None,
        }


class IndicatorRule(Base):
    """A persisted indicator rule: bind a source data table + date/value column
    + math op to an output indicator name, replayable via run_indicator.

    `datasource` is a soft reference to daas `sources.name` (no FK, matching
    `ProcessRule.datasource`). `run_indicator` upserts results into the daas
    `observations` table — the project's existing indicator store — keyed on
    (source=datasource, function_name, indicator=indicator_name, date).
    """
    __tablename__ = "indicator_rules"
    __table_args__ = (UniqueConstraint("name", name="uq_indicator_rule_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    datasource = Column(String(128), nullable=False)  # daas sources.name (soft ref)
    function_name = Column(String(255), nullable=False)
    source_table = Column(String(128), nullable=False)
    date_column = Column(String(128), nullable=False)
    value_column = Column(String(128), nullable=False)
    op = Column(String(64), nullable=False)
    params_json = Column(JSON, nullable=True)
    indicator_name = Column(String(255), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "datasource": self.datasource,
            "function_name": self.function_name,
            "source_table": self.source_table,
            "date_column": self.date_column,
            "value_column": self.value_column,
            "op": self.op,
            "params": self.params_json or {},
            "indicator_name": self.indicator_name,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ═══════════════════════════════════════════════════════════════
# entity domain — stocks + countries, linked to daas `sources`
# ═══════════════════════════════════════════════════════════════


class Entity(Base):
    """A reference entity — a stock (multi-market) or a country.

    Linked to daas `sources` via `EntityDatasourceLink` so an agent can
    answer "what data can I get for this entity" in one lookup. Natural key
    is `(entity_type, code)`: for stocks `code` is the canonical market code
    (6-digit A-share, 5-digit HK, US ticker); for countries it's ISO 3166-1
    alpha-2. `ticker` is stored separately for sources that expect the
    ticker form (yfinance/edgar).
    """
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("entity_type", "code", name="uq_entity_type_code"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(32), nullable=False, index=True)  # 'stock' | 'country'
    code = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    ticker = Column(String(64), nullable=True, index=True)
    exchange = Column(String(32), nullable=True)  # SSE / SZSE / NASDAQ / NYSE / HKEX / ...
    country_code = Column(String(8), nullable=True, index=True)  # ISO 3166-1 alpha-2
    isin = Column(String(16), nullable=True)
    aliases = Column(JSON, nullable=True)  # ["贵州茅台", "Kweichow Moutai", ...]
    status = Column(String(16), nullable=False, default="active")  # active | delisted
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    links = relationship(
        "EntityDatasourceLink",
        back_populates="entity",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "code": self.code,
            "name": self.name,
            "ticker": self.ticker,
            "exchange": self.exchange,
            "country_code": self.country_code,
            "isin": self.isin,
            "aliases": self.aliases or [],
            "status": self.status,
            "metadata": self.metadata_ or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EntityDatasourceLink(Base):
    """Many-to-many between entities and daas `sources`.

    `identifier_in_source` is the value to plug into that datasource's
    lookup tool (e.g. for AAPL → yfinance: 'AAPL'; → edgar: 'AAPL' since
    get_company accepts a ticker; → cnreport for 600519: '600519'). The
    coverage tool substitutes this into the section routing instruction so
    the result is directly executable.
    """
    __tablename__ = "entity_datasource_links"
    __table_args__ = (UniqueConstraint("entity_id", "source_id", name="uq_entity_source"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id = Column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_in_source = Column(String(128), nullable=True)
    coverage = Column(String(16), nullable=False, default="full")  # full | partial | none
    metadata_ = Column("metadata", JSON, nullable=True)
    last_fetched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    entity = relationship("Entity", back_populates="links")
    source = relationship("DaasSource", lazy="selectin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_id": self.entity_id,
            "source_id": self.source_id,
            "identifier_in_source": self.identifier_in_source,
            "coverage": self.coverage,
            "metadata": self.metadata_ or {},
            "last_fetched_at": self.last_fetched_at.isoformat() if self.last_fetched_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════════
# leader-mcp domain — CrewAI specialist data agents + data workflows
# (crewai-data-workflow capability). Each specialist agent binds to one
# leader_upstreams row; workflows compose ordered steps over those agents.
# upstreams/agents are soft refs (no FK) so rename/disable flows aren't
# blocked; workflow→step and run→result are real FKs with ON DELETE CASCADE.
# ═══════════════════════════════════════════════════════════════


class SpecialistAgent(Base):
    """A CrewAI specialist agent bound to exactly one data-fetch MCP upstream.

    `upstream` is a soft reference to `leader_upstreams.name` (the agent can
    only fetch from this MCP). `model` names an entry in the `LEADER_MODELS`
    registry (null → shared `LLM_*` fallback). The agent's `call_data_mcp`
    tool is curried to `upstream` at run time so it cannot fetch elsewhere.
    """

    __tablename__ = "specialist_agents"
    __table_args__ = (UniqueConstraint("name", name="uq_specialist_agent_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    upstream = Column(String(64), nullable=False, index=True)  # leader_upstreams.name (soft ref)
    role = Column(String(255), nullable=False)
    goal = Column(Text, nullable=False)
    backstory = Column(Text, nullable=True)
    model = Column(String(64), nullable=True)  # LEADER_MODELS name; null = shared LLM_* fallback
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self, upstream_missing: bool = False) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "upstream": self.upstream,
            "upstream_missing": upstream_missing,
            "role": self.role,
            "goal": self.goal,
            "backstory": self.backstory,
            "model": self.model,
            "enabled": bool(self.enabled),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Workflow(Base):
    """A named, ordered workflow of data-fetch steps over specialist agents."""

    __tablename__ = "workflows"
    __table_args__ = (UniqueConstraint("name", name="uq_workflow_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    steps = relationship(
        "WorkflowStep",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.sort_order",
        lazy="selectin",
    )
    runs = relationship(
        "WorkflowRun",
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "step_count": len(self.steps) if self.steps else 0,
        }


class WorkflowStep(Base):
    """One step in a workflow: a specialist agent + a request (+ optional deps).

    `depends_on` is a comma-separated list of prior step `sort_order` values
    whose raw output is injected as text context into this step's request.
    `on_fail` is "continue" (default — record error, keep going) or "stop".
    `model` optionally overrides the agent's bound model for this step only.
    """

    __tablename__ = "workflow_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(
        Integer,
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order = Column(Integer, nullable=False)
    agent = Column(String(128), nullable=False)  # specialist_agents.name (soft ref)
    request = Column(Text, nullable=False)
    depends_on = Column(String(255), nullable=True)  # "1,2" → inject prior step outputs
    on_fail = Column(String(16), nullable=False, default="continue")  # continue | stop
    model = Column(String(64), nullable=True)  # optional per-step override
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    workflow = relationship("Workflow", back_populates="steps")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "sort_order": self.sort_order,
            "agent": self.agent,
            "request": self.request,
            "depends_on": [s.strip() for s in (self.depends_on or "").split(",") if s.strip()]
            if self.depends_on
            else [],
            "on_fail": self.on_fail,
            "model": self.model,
            "enabled": bool(self.enabled),
        }


class WorkflowRun(Base):
    """One execution of a workflow (full or partial). A run left `in_progress`
    is resumed by `run_workflow_step`; `run_workflow` always starts fresh."""

    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(
        Integer,
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(16), nullable=False, default="running")  # running|in_progress|completed|failed
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)

    workflow = relationship("Workflow", back_populates="runs")
    results = relationship(
        "WorkflowStepResult",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="WorkflowStepResult.step_sort_order",
        lazy="selectin",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class WorkflowStepResult(Base):
    """The captured result of one step in one run. `output_json` holds the raw
    upstream data the specialist agent fetched (truncated at 1 MB with a
    `_truncated` flag when larger). `meta_json` records fallback reasons etc.
    Unique on (run_id, step_sort_order) so re-running a step is an upsert."""

    __tablename__ = "workflow_step_results"
    __table_args__ = (
        UniqueConstraint("run_id", "step_sort_order", name="uq_workflow_step_result"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(
        Integer,
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_sort_order = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="running")  # running|completed|failed
    output_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    meta_json = Column(Text, nullable=True)  # e.g. {"fallback":"direct","reason":"..."}
    ran_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    run = relationship("WorkflowRun", back_populates="results")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "step_sort_order": self.step_sort_order,
            "status": self.status,
            "output": _json_loads(self.output_json),
            "error": self.error,
            "meta": _json_loads(self.meta_json),
            "ran_at": self.ran_at.isoformat() if self.ran_at else None,
        }
