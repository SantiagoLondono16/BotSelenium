import uuid
from datetime import date, datetime

from pydantic import BaseModel


class RecordOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    external_row_id: str | None
    patient_name: str | None
    patient_document: str | None
    date_service_or_facturation: date | None
    site: str | None
    contract: str | None
    raw_row_json: dict
    captured_at: datetime

    model_config = {"from_attributes": True}


class PaginatedRecords(BaseModel):
    total: int
    page: int
    size: int
    items: list[RecordOut]
