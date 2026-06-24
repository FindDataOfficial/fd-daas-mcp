"""
SQLAlchemy models for daas-mcp — standalone copy for MCP server independence.

Mirrors the harness models but lives in the MCP directory so the server
can run without depending on the harness package.
"""
from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    String,
    JSON,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    DateTime,
    func,
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, index=True)
    label = Column(String(128), nullable=False)
    description = Column(String, nullable=True)
    url = Column(String(512), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    functions = relationship(
        "Function", back_populates="source", cascade="all, delete-orphan", lazy="selectin"
    )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "url": self.url,
            "enabled": self.enabled,
            "config": self.config or {},
        }


class Function(Base):
    __tablename__ = "functions"
    __table_args__ = (
        UniqueConstraint("source_id", "name", name="uq_source_function"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    label = Column(String(255), nullable=True)
    description = Column(String, nullable=True)
    category = Column(String(255), nullable=False, default="未分类")
    parameters = Column(JSON, nullable=True)
    output_type = Column(String(64), default="DataFrame")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    source = relationship("Source", back_populates="functions")
    columns = relationship(
        "FunctionColumn",
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


class FunctionColumn(Base):
    __tablename__ = "function_columns"
    __table_args__ = (
        UniqueConstraint("function_id", "name", name="uq_function_column"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    function_id = Column(
        Integer, ForeignKey("functions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    label = Column(String(255), nullable=True)
    type = Column(String(64), nullable=True)
    description = Column(String, nullable=True)
    nullable = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    function = relationship("Function", back_populates="columns")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "description": self.description,
            "nullable": self.nullable,
        }
