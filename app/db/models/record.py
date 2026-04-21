import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Use JSONB in PostgreSQL (binary, indexable) and fall back to plain JSON in
# SQLite (used by the in-memory test database).
_JSONB_OR_JSON = JSONB().with_variant(JSON(), "sqlite")

from app.db.base import Base


class Record(Base):
    __tablename__ = "records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Fields extracted from the portal table ────────────────────────────────
    # All are nullable: populated once DOM selectors are verified and the RPA
    # maps cell positions to these named keys.  raw_row_json is always written.

    external_row_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        comment="Row identifier as it appears in the portal (e.g. invoice number)",
    )
    patient_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    patient_document: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="National ID / document number of the patient",
    )
    date_service_or_facturation: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Service date or invoice date, whichever the portal column represents",
    )
    site: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        comment="Clinic / service location name",
    )
    contract: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        comment="Insurance contract or payer name",
    )

    # Full raw dict from the extraction step — always populated regardless of
    # whether named columns could be mapped.  Enables schema-free querying and
    # acts as the source of truth for re-processing.
    raw_row_json: Mapped[dict] = mapped_column(_JSONB_OR_JSON, nullable=False)

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["Job"] = relationship("Job", back_populates="records")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Record id={self.id} job_id={self.job_id} patient={self.patient_document!r}>"
