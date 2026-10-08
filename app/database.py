from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier():
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "generation_jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    course_name: Mapped[str]
    issue_date: Mapped[str]
    template_version: Mapped[str] = mapped_column(default="1")
    status: Mapped[str] = mapped_column(default="queued", index=True)
    total_count: Mapped[int]
    created_at: Mapped[str] = mapped_column(default=now)
    started_at: Mapped[str | None]
    completed_at: Mapped[str | None]


class Item(Base):
    __tablename__ = "certificate_items"
    __table_args__ = (UniqueConstraint("job_id", "input_index"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=identifier)
    job_id: Mapped[str] = mapped_column(ForeignKey("generation_jobs.id"), index=True)
    input_index: Mapped[int]
    client_reference: Mapped[str | None]
    recipient_name: Mapped[str | None]
    email: Mapped[str | None]
    status: Mapped[str] = mapped_column(index=True)
    certificate_id: Mapped[str | None] = mapped_column(unique=True)
    output_key: Mapped[str | None]
    error_stage: Mapped[str | None]
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]
    attempt_count: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[str | None]
    completed_at: Mapped[str | None]


def connect(settings, initialize=True):
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    url = settings.database_url
    if url.startswith(("postgres://", "postgresql://")):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def configure(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA journal_mode=WAL")
    if initialize:
        Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)
