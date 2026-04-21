"""Tests for GET /records and GET /records/{id}."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.job_service import create_job
from app.services.record_service import create_records


def _sample_row(**overrides) -> dict:
    """Build a minimal row dict matching the Record field contract."""
    base = {
        "external_row_id": "INV-001",
        "patient_name": "Ana García",
        "patient_document": "12345678",
        "date_service_or_facturation": "2024-01-15",
        "site": "Clínica Norte",
        "contract": "Plan Salud A",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_list_records_empty(client: AsyncClient) -> None:
    response = await client.get("/records")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_records_filter_by_job_id(client: AsyncClient, db_session: AsyncSession) -> None:
    job_a = await create_job(db_session, date(2024, 1, 1), date(2024, 1, 31), limit_requested=5)
    job_b = await create_job(db_session, date(2024, 2, 1), date(2024, 2, 28), limit_requested=5)
    await db_session.commit()

    await create_records(
        db_session,
        job_a.id,
        [_sample_row(external_row_id="INV-001"), _sample_row(external_row_id="INV-002")],
    )
    await create_records(db_session, job_b.id, [_sample_row(external_row_id="INV-003")])
    await db_session.commit()

    response = await client.get(f"/records?job_id={job_a.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_get_record_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/records/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_record_detail(client: AsyncClient, db_session: AsyncSession) -> None:
    job = await create_job(db_session, date(2024, 5, 1), date(2024, 5, 31), limit_requested=10)
    await db_session.commit()
    row = _sample_row(patient_name="Carlos López", patient_document="87654321")
    records = await create_records(db_session, job.id, [row])
    await db_session.commit()

    response = await client.get(f"/records/{records[0].id}")
    assert response.status_code == 200
    data = response.json()
    assert data["patient_name"] == "Carlos López"
    assert data["patient_document"] == "87654321"
    assert data["external_row_id"] == "INV-001"
    assert data["raw_row_json"]["patient_name"] == "Carlos López"


@pytest.mark.asyncio
async def test_record_raw_row_json_stores_full_dict(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """raw_row_json must persist every key, including unexpected ones."""
    job = await create_job(db_session, date(2024, 6, 1), date(2024, 6, 30), limit_requested=1)
    await db_session.commit()
    row = {"col_0": "unknown", "col_1": "data", "extra_field": "value"}
    records = await create_records(db_session, job.id, [row])
    await db_session.commit()

    response = await client.get(f"/records/{records[0].id}")
    assert response.status_code == 200
    data = response.json()
    assert data["raw_row_json"]["extra_field"] == "value"
    assert data["patient_name"] is None  # named column stays NULL for unknown rows
