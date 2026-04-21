"""Tests for GET /jobs and GET /jobs/{id}."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.job_service import create_job, mark_job_success


@pytest.mark.asyncio
async def test_list_jobs_empty(client: AsyncClient) -> None:
    response = await client.get("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_jobs_returns_created_job(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_job(db_session, date(2024, 1, 1), date(2024, 1, 31), limit_requested=10)
    await db_session.commit()

    response = await client.get("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_list_jobs_filter_by_status(client: AsyncClient, db_session: AsyncSession) -> None:
    job = await create_job(db_session, date(2024, 1, 1), date(2024, 1, 31), limit_requested=5)
    await db_session.commit()
    await mark_job_success(db_session, job.id, total_extracted=5)
    await db_session.commit()

    response = await client.get("/jobs?status=success")
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = await client.get("/jobs?status=pending")
    assert response.status_code == 200
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_get_job_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/jobs/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_job_detail(client: AsyncClient, db_session: AsyncSession) -> None:
    job = await create_job(db_session, date(2024, 3, 1), date(2024, 3, 31), limit_requested=50)
    await db_session.commit()

    response = await client.get(f"/jobs/{job.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(job.id)
    assert data["status"] == "pending"
    assert data["limit_requested"] == 50
