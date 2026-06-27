"""
SQLAlchemy models for yfinance function registry.

Mirrors the akshare harness two-table design:
  - functions: one row per yfinance command (command, category, source, description, parameters)
  - function_columns: one row per output column (1:N from functions)
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Function(Base):
    __tablename__ = "functions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command = Column(String(255), unique=True, nullable=False, index=True)
    category = Column(String(255), nullable=False, default="未分类")
    source = Column(String(512), nullable=True)
    description = Column(String, nullable=True)
    parameters = Column(JSON, nullable=True)

    columns = relationship(
        "FunctionColumn",
        back_populates="function",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def toDict(self) -> dict:
        """Serialize to dict matching the registry.json format."""
        return {
            "command": self.command,
            "category": self.category,
            "source": self.source,
            "description": self.description,
            "parameters": self.parameters or [],
            "columns": [c.toDict() for c in self.columns] if self.columns else [],
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

    function = relationship("Function", back_populates="columns")

    def toDict(self) -> dict:
        """Serialize to dict matching the registry.json column format."""
        return {
            "name": self.column_name,
            "type": self.column_type,
            "description": self.column_description,
        }
