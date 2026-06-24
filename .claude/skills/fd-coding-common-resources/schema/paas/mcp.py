"""
SQLAlchemy schema for MCP PAAS
Generated from diagram/paas/mcp-diagram.yaml
"""
from sqlalchemy import Column, String, Integer, JSON, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# ============================================
# Data entities
# ============================================

class MCPServer(Base):
    __tablename__ = "mcp_server"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    source_path = Column(String(512), nullable=False)
    entry_point = Column(String(255), nullable=False, default="server:app")
    runtime_config = Column(JSON, nullable=True)
    port = Column(Integer, nullable=False)
    health_url = Column(String(512), nullable=False)
    status = Column(String(32), nullable=False, default="stopped")
    process_id = Column(Integer, nullable=True)


# ============================================
# Skipped service classes (not persistable)
# ============================================
# ServerRegistry: YAML file storage per clear-goal design, not a database table
# PortAllocator: runtime port assignment in memory, no persistence needed
# LifecycleManager: process management + health polling + log collection, all runtime
# NginxConfigManager: filesystem config generation, no database state
# ServerRouter: FastAPI route orchestration layer, stateless
# DockerDeployer: Docker CLI wrapper, dockerAvailable is a runtime detection flag

# ============================================
# Skipped relationships (both endpoints are not data entities)
# ============================================
# ServerRegistry --composition--> MCPServer: ServerRegistry is YAML-based, not a model
# LifecycleManager --composition--> PortAllocator: both are runtime services
# LifecycleManager --association--> ServerRegistry: runtime read, no FK
# NginxConfigManager --association--> ServerRegistry: runtime read, no FK
# ServerRouter --association--> ServerRegistry: runtime, no FK
# ServerRouter --association--> LifecycleManager: runtime, no FK
# ServerRouter --dependency--> NginxConfigManager: runtime delegation, no FK
# DockerDeployer --association--> LifecycleManager: runtime extension, no FK
