"""SQLAlchemy models for schedules and executions."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
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

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    schedule_id = Column(String, nullable=False, index=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending")  # pending, running, completed, failed
    output = Column(Text, nullable=True)


class Task(Base):
    """User-defined tasks stored in the database — no source-code changes needed."""

    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    name = Column(String, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    command = Column(Text, nullable=False)  # shell command or script path + args
    timeout = Column(Integer, default=60)  # seconds
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
