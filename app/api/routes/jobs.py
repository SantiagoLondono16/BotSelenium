import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.logging import get_logger
from app.db.models.job import JobStatus
from app.schemas.job import JobDetail, JobSummary, PaginatedJobs
from app.services import job_service

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "",
    response_model=PaginatedJobs,
    summary="List all extraction jobs",
    description="Returns a paginated list of jobs, optionally filtered by status.",
)
async def list_jobs(
    status: JobStatus | None = Query(
        default=None,
        description="Filter by job status: pending | running | success | failed",
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    size: int = Query(default=20, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_session),
) -> PaginatedJobs:
    total, jobs = await job_service.list_jobs(db, status=status, page=page, size=size)
    logger.debug("jobs_listed", total=total, page=page, size=size, status_filter=status)
    return PaginatedJobs(
        total=total,
        page=page,
        size=size,
        items=[JobSummary.model_validate(j) for j in jobs],
    )


@router.get(
    "/{job_id}",
    response_model=JobDetail,
    summary="Get a single job by ID",
    description=(
        "Returns the full detail of a job including status, timestamps, "
        "total rows extracted, and any error message."
    ),
)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_session),
) -> JobDetail:
    job = await job_service.get_job(db, job_id)
    if job is None:
        logger.warning("job_not_found", job_id=str(job_id))
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobDetail.model_validate(job)
