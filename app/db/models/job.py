import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobStatus(StrEnum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="jobstatus"), nullable=False, default=JobStatus.pending
    )
    fecha_inicial: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_final: Mapped[date] = mapped_column(Date, nullable=False)
    limit_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    total_extracted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    records: Mapped[list["Record"]] = relationship(  # noqa: F821
        "Record", back_populates="job", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} status={self.status}>"
