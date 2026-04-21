import asyncio

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.core.logging import get_logger
from app.rpa.bot import run_extraction_job
from app.schemas.job import ExtractRequest, ExtractResponse
from app.services import job_service

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/extract",
    response_model=ExtractResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger an RPA extraction job",
    description=(
        "Validates the date range and row limit, persists a Job record in `pending` "
        "status, then fires the RPA bot in a background thread. "
        "Returns immediately — poll `GET /jobs/{job_id}` to track progress."
    ),
)
async def trigger_extraction(
    payload: ExtractRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> ExtractResponse:
    job = await job_service.create_job(
        db,
        fecha_inicial=payload.fecha_inicial,
        fecha_final=payload.fecha_final,
        limit_requested=payload.limit_requested,
    )
    await db.commit()

    logger.info(
        "rpa_job_queued",
        job_id=str(job.id),
        fecha_inicial=str(payload.fecha_inicial),
        fecha_final=str(payload.fecha_final),
        limit_requested=payload.limit_requested,
    )

    # get_running_loop() is correct inside an async context (replaces the
    # deprecated get_event_loop()).  We intentionally do not await the Future —
    # the bot runs in the background and updates its own DB row when done.
    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        request.app.state.thread_pool,
        run_extraction_job,
        str(job.id),
        str(payload.fecha_inicial),
        str(payload.fecha_final),
        payload.limit_requested,
    )

    return ExtractResponse(job_id=job.id, status=job.status)
