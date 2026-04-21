import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.db.models.job import JobStatus


class ExtractRequest(BaseModel):
    fecha_inicial: date = Field(..., description="Start date for the extraction filter")
    fecha_final: date = Field(..., description="End date for the extraction filter")
    limit_requested: int = Field(..., ge=1, le=10_000, description="Maximum rows to extract")

    @model_validator(mode="after")
    def validate_date_range(self) -> "ExtractRequest":
        if self.fecha_inicial > self.fecha_final:
            raise ValueError("fecha_inicial must be on or before fecha_final")
        return self


class ExtractResponse(BaseModel):
    job_id: uuid.UUID
    status: JobStatus

    model_config = {"from_attributes": True}


class JobSummary(BaseModel):
    id: uuid.UUID
    status: JobStatus
    fecha_inicial: date
    fecha_final: date
    limit_requested: int
    total_extracted: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobDetail(JobSummary):
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class PaginatedJobs(BaseModel):
    total: int
    page: int
    size: int
    items: list[JobSummary]
