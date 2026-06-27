"""
Unified SQLAlchemy models for multi-harness registry.

All CLI-Anything harness registries share this schema in one database.
The `harness` column distinguishes which harness each function belongs to
(e.g., 'akshare', 'minimax', 'mailchimp').
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Function(Base):
    __tablename__ = "functions"
    __table_args__ = (
        UniqueConstraint("harness", "command", name="uq_harness_command"),
    )

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
        "FunctionColumn",
        back_populates="function",
        cascade="all, delete-orphan",
        lazy="selectin",
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
        Integer,
        ForeignKey("functions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    __table_args__ = (
        UniqueConstraint("function_id", "params_json", name="uq_snapshot_function_params"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    function_id = Column(
        Integer,
        ForeignKey("functions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    params_json = Column(JSON, nullable=False)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(16), default="success")  # success, partial, error
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
