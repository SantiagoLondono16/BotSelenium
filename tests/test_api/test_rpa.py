"""Tests for POST /rpa/extract."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_extract_returns_202(client: AsyncClient) -> None:
    # Patch at the route module level so run_in_executor receives the mock.
    # The import is now module-level in rpa.py, so patching the name there works.
    with patch("app.api.routes.rpa.run_extraction_job"):
        response = await client.post(
            "/rpa/extract",
            json={
                "fecha_inicial": "2024-01-01",
                "fecha_final": "2024-01-31",
                "limit_requested": 10,
            },
        )
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_extract_invalid_date_range(client: AsyncClient) -> None:
    response = await client.post(
        "/rpa/extract",
        json={
            "fecha_inicial": "2024-02-01",
            "fecha_final": "2024-01-01",  # before fecha_inicial
            "limit_requested": 10,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_extract_invalid_limit_zero(client: AsyncClient) -> None:
    response = await client.post(
        "/rpa/extract",
        json={
            "fecha_inicial": "2024-01-01",
            "fecha_final": "2024-01-31",
            "limit_requested": 0,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_extract_missing_fields(client: AsyncClient) -> None:
    response = await client.post("/rpa/extract", json={"limit_requested": 5})
    assert response.status_code == 422
