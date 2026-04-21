import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.logging import get_logger
from app.schemas.record import PaginatedRecords, RecordOut
from app.services import record_service

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "",
    response_model=PaginatedRecords,
    summary="List extracted records",
    description=(
        "Returns a paginated list of records. "
        "Filter by `job_id` to retrieve all rows from a specific extraction run."
    ),
)
async def list_records(
    job_id: uuid.UUID | None = Query(
        default=None, description="Return only records belonging to this job"
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    size: int = Query(default=20, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_session),
) -> PaginatedRecords:
    total, records = await record_service.list_records(db, job_id=job_id, page=page, size=size)
    logger.debug("records_listed", total=total, page=page, job_id=str(job_id))
    return PaginatedRecords(
        total=total,
        page=page,
        size=size,
        items=[RecordOut.model_validate(r) for r in records],
    )


@router.get(
    "/{record_id}",
    response_model=RecordOut,
    summary="Get a single record by ID",
    description="Returns the full detail of one extracted record including raw_row_json.",
)
async def get_record(
    record_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> RecordOut:
    record = await record_service.get_record(db, record_id)
    if record is None:
        logger.warning("record_not_found", record_id=str(record_id))
        raise HTTPException(status_code=404, detail=f"Record {record_id} not found")
    return RecordOut.model_validate(record)
