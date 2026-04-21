from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", env=settings.app_env)
    app.state.thread_pool = ThreadPoolExecutor(max_workers=settings.rpa_max_workers)
    yield
    logger.info("shutdown")
    app.state.thread_pool.shutdown(wait=False)


def create_app() -> FastAPI:
    from app.api.routes import jobs, records, rpa

    application = FastAPI(
        title="RPA Extraction API",
        version="1.0.0",
        description="Selenium RPA bot orchestration API",
        lifespan=lifespan,
    )

    @application.get("/health", tags=["Health"], summary="Liveness check")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "version": "1.0.0"})

    application.include_router(rpa.router, prefix="/rpa", tags=["RPA"])
    application.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
    application.include_router(records.router, prefix="/records", tags=["Records"])

    return application


app = create_app()
