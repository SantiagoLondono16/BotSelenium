import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.record import Record

logger = get_logger(__name__)


def _parse_date(value: str | None) -> date | None:
    """Best-effort ISO date parse; returns None on failure."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


async def create_records(
    db: AsyncSession,
    job_id: uuid.UUID,
    rows: list[dict],
) -> list[Record]:
    """
    Persist extracted rows as Record objects.

    Each dict in `rows` is always stored verbatim in `raw_row_json`.
    Named columns are populated from well-known keys when present; until DOM
    selectors are verified and the RPA maps them, they remain NULL.

    Expected keys (optional, populated by extraction once selectors are known):
      external_row_id, patient_name, patient_document,
      date_service_or_facturation, site, contract
    """
    records = [
        Record(
            job_id=job_id,
            external_row_id=row.get("external_row_id"),
            patient_name=row.get("patient_name"),
            patient_document=row.get("patient_document"),
            date_service_or_facturation=_parse_date(row.get("date_service_or_facturation")),
            site=row.get("site"),
            contract=row.get("contract"),
            raw_row_json=row,
        )
        for row in rows
    ]
    db.add_all(records)
    await db.flush()
    logger.info("records_persisted", job_id=str(job_id), count=len(records))
    return records


async def get_record(db: AsyncSession, record_id: uuid.UUID) -> Record | None:
    result = await db.execute(select(Record).where(Record.id == record_id))
    return result.scalar_one_or_none()


async def list_records(
    db: AsyncSession,
    job_id: uuid.UUID | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[int, list[Record]]:
    query = select(Record)
    count_query = select(func.count()).select_from(Record)

    if job_id is not None:
        query = query.where(Record.job_id == job_id)
        count_query = count_query.where(Record.job_id == job_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(Record.captured_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    records = list(result.scalars().all())

    return total, records
