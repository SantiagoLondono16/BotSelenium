import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.job import Job, JobStatus

logger = get_logger(__name__)


class JobNotFoundError(Exception):
    """Raised when a job_id does not exist in the database."""


# ── Public read operations ────────────────────────────────────────────────────


async def create_job(
    db: AsyncSession,
    fecha_inicial: date,
    fecha_final: date,
    limit_requested: int,
) -> Job:
    job = Job(
        fecha_inicial=fecha_inicial,
        fecha_final=fecha_final,
        limit_requested=limit_requested,
        status=JobStatus.pending,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    logger.info("job_created", job_id=str(job.id))
    return job


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> Job | None:
    """Return the Job or None — used by API routes for 404 handling."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def list_jobs(
    db: AsyncSession,
    status: JobStatus | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[int, list[Job]]:
    query = select(Job)
    count_query = select(func.count()).select_from(Job)

    if status is not None:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(Job.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    jobs = list(result.scalars().all())

    return total, jobs


# ── Public write operations (used by bot.py) ──────────────────────────────────


async def mark_job_running(db: AsyncSession, job_id: uuid.UUID) -> None:
    """
    Transition Job to running status and record started_at.

    Raises:
        JobNotFoundError: if `job_id` does not exist in the database.
            This prevents the bot from proceeding silently when the DB row
            is missing (e.g. race condition or accidental deletion).
    """
    job = await _get_job_or_raise(db, job_id)
    job.status = JobStatus.running
    job.started_at = datetime.now(UTC)
    await db.flush()
    logger.info("job_running", job_id=str(job_id))


async def mark_job_success(
    db: AsyncSession,
    job_id: uuid.UUID,
    total_extracted: int,
) -> None:
    """
    Transition Job to success status, record finished_at and row count.

    Raises:
        JobNotFoundError: if `job_id` does not exist.
    """
    job = await _get_job_or_raise(db, job_id)
    job.status = JobStatus.success
    job.total_extracted = total_extracted
    job.finished_at = datetime.now(UTC)
    await db.flush()
    logger.info("job_success", job_id=str(job_id), total_extracted=total_extracted)


async def mark_job_failed(
    db: AsyncSession,
    job_id: uuid.UUID,
    error_message: str,
) -> None:
    """
    Transition Job to failed status and persist the error message.

    Raises:
        JobNotFoundError: if `job_id` does not exist.
    """
    job = await _get_job_or_raise(db, job_id)
    job.status = JobStatus.failed
    job.error_message = error_message
    job.finished_at = datetime.now(UTC)
    await db.flush()
    logger.error("job_failed", job_id=str(job_id), error=error_message)


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _get_job_or_raise(db: AsyncSession, job_id: uuid.UUID) -> Job:
    """
    Fetch a Job row and raise JobNotFoundError if it does not exist.
    Used exclusively by the mutation operations above.
    """
    job = await get_job(db, job_id)
    if job is None:
        raise JobNotFoundError(
            f"Job {job_id} not found — it may have been deleted or never committed."
        )
    return job
