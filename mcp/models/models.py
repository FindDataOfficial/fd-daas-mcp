"""Single source of truth for all database schemas across the MCP ecosystem.

Every MCP server and the dashboard share this one Base. Schema changes
MUST be made here first, then reflected in consuming code.

Domains:
  leader-mcp:  Function, FunctionColumn, DataSnapshot (harness-based registry)
  cron-mcp:    Schedule, Execution, Task (scheduler data)
  daas-mcp:    DaasSource, DaasFunction, DaasFunctionColumn, Observation (source-based registry)
  scrapling:   ScrawConfig (scraping configs)
  dashboard:   Datasource, DatasourceColumn (dashboard metadata)
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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    functions = relationship(
        "DaasFunction", back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "url": self.url,
            "enabled": self.enabled,
            "config": self.config or {},
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
