"""
RPA orchestrator — bot.py

Entry point for the ThreadPoolExecutor.  Owns the complete Job lifecycle and
coordinates all RPA sub-modules in order.

Execution model
───────────────
- Called from a background thread via loop.run_in_executor() in rpa.py.
- Creates its own asyncio event loop — the FastAPI event loop must never be
  shared across threads.
- Every log entry carries job_id via structlog context binding.

Job lifecycle
─────────────
  pending
    │  (route commits Job row, dispatches this function)
    ▼
  running  ← mark_job_running()
    │
    ├─ open browser
    ├─ login
    ├─ navigate to Generar Factura
    ├─ apply date filters + click Buscar
    ├─ extract rows up to limit_requested
    ├─ persist records (linked to job_id)
    │
    ├──► success   ← mark_job_success(total_extracted)
    └──► failed    ← mark_job_failed(error_message)

Error contract
──────────────
Known RPA errors (LoginError, NavigationError, FilterError, ExtractionError)
are caught, logged, and stored in error_message.

Unexpected errors (e.g. DB failure, programmer mistakes) are also caught so
the job is never stuck in "running" indefinitely.

All DB calls inside this thread use _safe_mark_failed() which logs but does
not re-raise, preventing a secondary DB error from masking the original cause.
"""

import asyncio
import uuid
from datetime import date

from app.core.logging import get_logger
from app.db.session import ThreadSessionLocal
from app.rpa.driver_factory import create_driver, quit_driver
from app.rpa.extractor import ExtractionError, extract_table_rows
from app.rpa.filters import FilterError, apply_filters_and_search
from app.rpa.login import LoginError, perform_login
from app.rpa.navigation import NavigationError, go_to_generar_factura
from app.services import job_service, record_service

logger = get_logger(__name__)

_KNOWN_RPA_ERRORS = (LoginError, NavigationError, FilterError, ExtractionError)

# Maximum characters stored in error_message to avoid unbounded DB writes.
_ERROR_MSG_MAX_LEN = 2_000


def run_extraction_job(
    job_id_str: str,
    fecha_inicial_str: str,
    fecha_final_str: str,
    limit_requested: int,
) -> None:
    """
    ThreadPoolExecutor entry point.  All arguments are plain Python scalars.

    Args:
        job_id_str:        String UUID of the already-committed Job row.
        fecha_inicial_str: ISO date "YYYY-MM-DD".
        fecha_final_str:   ISO date "YYYY-MM-DD".
        limit_requested:   Maximum rows to extract.
    """
    job_id = uuid.UUID(job_id_str)
    fecha_inicial = date.fromisoformat(fecha_inicial_str)
    fecha_final = date.fromisoformat(fecha_final_str)

    log = logger.bind(job_id=job_id_str)
    log.info("bot_start", limit_requested=limit_requested)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    driver = None
    try:
        # ── Phase 1: mark running ─────────────────────────────────────────────
        # Separated from the RPA try/except so a DB failure here is handled
        # distinctly — we still attempt to mark the job as failed before exiting.
        try:
            loop.run_until_complete(_set_running(job_id))
        except Exception as exc:
            error_msg = _format_error("DB error before start", exc)
            log.error("bot_db_error_before_start", error=error_msg)
            _safe_mark_failed(loop, job_id, error_msg, log)
            return  # nothing to clean up — driver was never opened

        # ── Phase 2: RPA execution ────────────────────────────────────────────
        try:
            log.info("bot_step", step="open_browser")
            driver = create_driver()

            log.info("bot_step", step="login")
            perform_login(driver)

            log.info("bot_step", step="navigate")
            go_to_generar_factura(driver)

            log.info(
                "bot_step",
                step="filter",
                fecha_inicial=str(fecha_inicial),
                fecha_final=str(fecha_final),
            )
            apply_filters_and_search(driver, fecha_inicial, fecha_final)

            log.info("bot_step", step="extract", limit_requested=limit_requested)
            rows = extract_table_rows(driver, limit_requested)

            log.info("bot_step", step="persist", row_count=len(rows))
            loop.run_until_complete(_persist(job_id, rows))

            loop.run_until_complete(_set_success(job_id, len(rows)))
            log.info("bot_complete", total_extracted=len(rows))

        except _KNOWN_RPA_ERRORS as exc:
            error_msg = _format_error(type(exc).__name__, exc)
            log.error("bot_rpa_error", step=type(exc).__name__, error=error_msg)
            _safe_mark_failed(loop, job_id, error_msg, log)

        except Exception as exc:
            error_msg = _format_error("Unexpected error", exc)
            log.exception("bot_unexpected_error", error=error_msg)
            _safe_mark_failed(loop, job_id, error_msg, log)

    finally:
        if driver is not None:
            quit_driver(driver)
        loop.close()
        log.info("bot_exit")


# ── Async DB helpers ──────────────────────────────────────────────────────────
# Each function opens its own ThreadSessionLocal session.
# Using ThreadSessionLocal (NullPool engine) is mandatory here because this
# code runs in a separate thread with its own event loop.  Sharing the main
# QueuePool engine across event loops corrupts asyncpg connections.


async def _set_running(job_id: uuid.UUID) -> None:
    async with ThreadSessionLocal() as db:
        await job_service.mark_job_running(db, job_id)
        await db.commit()


async def _persist(job_id: uuid.UUID, rows: list[dict]) -> None:
    async with ThreadSessionLocal() as db:
        await record_service.create_records(db, job_id, rows)
        await db.commit()


async def _set_success(job_id: uuid.UUID, total_extracted: int) -> None:
    async with ThreadSessionLocal() as db:
        await job_service.mark_job_success(db, job_id, total_extracted)
        await db.commit()


async def _set_failed(job_id: uuid.UUID, error_message: str) -> None:
    async with ThreadSessionLocal() as db:
        await job_service.mark_job_failed(db, job_id, error_message)
        await db.commit()


# ── Internal utilities ────────────────────────────────────────────────────────


def _safe_mark_failed(
    loop: asyncio.AbstractEventLoop, job_id: uuid.UUID, error_msg: str, log
) -> None:
    """
    Attempt to mark the job as failed without raising.

    This is used inside error handlers where a secondary exception from the DB
    must not mask the original failure.  Errors from this call are logged but
    swallowed so the calling code can continue to its finally block cleanly.
    """
    try:
        loop.run_until_complete(_set_failed(job_id, error_msg))
    except Exception as db_exc:
        # The job may remain in an intermediate state.  Log clearly so an
        # operator can fix it manually via the admin or a DB query.
        log.error(
            "bot_failed_to_mark_failed",
            job_id=str(job_id),
            db_error=str(db_exc),
            original_error=error_msg,
        )


def _format_error(prefix: str, exc: Exception) -> str:
    """Build a concise, bounded error string for storage in error_message."""
    msg = f"{prefix}: {exc}"
    if len(msg) > _ERROR_MSG_MAX_LEN:
        msg = msg[:_ERROR_MSG_MAX_LEN] + "… [truncated]"
    return msg
