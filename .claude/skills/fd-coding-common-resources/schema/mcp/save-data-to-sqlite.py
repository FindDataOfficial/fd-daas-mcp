"""
SQLAlchemy schema for AKShare registry
Generated from diagram/mcp/save-data-to-sqlite-diagram.yaml

Replaces the JSON-based registry with a normalized two-table design:
  - functions: one row per AKShare function (command, category, source, description, parameters)
  - function_columns: one row per output column (1:N from functions)
"""
from sqlalchemy import Column, Integer, String, JSON, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


# ============================================
# Data entities
# ============================================

class Function(Base):
    __tablename__ = "functions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    command = Column(String(255), unique=True, nullable=False, index=True)
    category = Column(String(255), nullable=False, default="未分类")
    source = Column(String(512), nullable=True)
    description = Column(String, nullable=True)
    parameters = Column(JSON, nullable=True)

    # Composition: Function owns its columns (cascade delete)
    columns = relationship(
        "FunctionColumn",
        back_populates="function",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def toDict(self):
        """Serialize to dict matching the original registry.json format."""
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

    # Back-reference to parent Function
    function = relationship("Function", back_populates="columns")

    def toDict(self):
        """Serialize to dict matching the original registry.json column format."""
        return {
            "name": self.column_name,
            "type": self.column_type,
            "description": self.column_description,
        }


# ============================================
# Skipped service classes (not persistable)
# ============================================
# Database: infrastructure — holds SQLAlchemy engine, session factory, and DATABASE_URL config.
#   Provides getSession(), initDb(), dispose(). Not a database table.
# RegistryService: query orchestration — takes a SQLAlchemy Session and wraps the five
#   registry operations (list, search, info, categories, categoryFunctions). Runtime only.
# MigrationRunner: one-shot utility — reads registry.json, upserts into the DB via Session,
#   verifies row counts. Not persistable.

# ============================================
# Skipped relationships (not both data entities)
# ============================================
# RegistryService --dependency--> Database: runtime session acquisition, no FK
# RegistryService --association--> Function: runtime queries via Session, no FK needed
# RegistryService --association--> FunctionColumn: runtime queries via Session, no FK needed
# MigrationRunner --dependency--> Database: runtime session acquisition, no FK
# MigrationRunner --dependency--> Function: populates rows at migration time, no FK needed
# MigrationRunner --dependency--> FunctionColumn: populates rows at migration time, no FK needed
