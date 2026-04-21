"""
Unit tests for the RPA bot orchestrator (bot.py).

All I/O is mocked — no browser, no database, no real event loop dependencies.
Tests verify that:
  - job status transitions happen in the correct order
  - records are persisted before success is marked
  - known RPA errors mark the job as failed with the error message
  - unexpected errors also mark the job as failed
  - the browser session is always closed (even on failure)
  - a DB failure on _set_running marks the job as failed and exits early
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.rpa.bot import run_extraction_job
from app.rpa.extractor import ExtractionError
from app.rpa.filters import FilterError
from app.rpa.login import LoginError
from app.rpa.navigation import NavigationError

# ── Shared fixtures ───────────────────────────────────────────────────────────

JOB_ID = str(uuid.uuid4())
FECHA_INICIAL = "2024-01-01"
FECHA_FINAL = "2024-01-31"
LIMIT = 10
SAMPLE_ROWS = [{"col_0": "Alice", "col_1": "doc001"}, {"col_0": "Bob", "col_1": "doc002"}]


def _run(
    *,
    rows=None,
    login_error=None,
    nav_error=None,
    filter_error=None,
    extract_error=None,
    set_running_error=None,
    persist_error=None,
):
    """
    Helper that runs run_extraction_job with all external dependencies mocked.
    Returns a dict of the mock objects for assertion.
    """
    if rows is None:
        rows = SAMPLE_ROWS

    with (
        patch("app.rpa.bot._set_running", new_callable=AsyncMock) as m_running,
        patch("app.rpa.bot._persist", new_callable=AsyncMock) as m_persist,
        patch("app.rpa.bot._set_success", new_callable=AsyncMock) as m_success,
        patch("app.rpa.bot._set_failed", new_callable=AsyncMock) as m_failed,
        patch("app.rpa.bot.create_driver") as m_create_driver,
        patch("app.rpa.bot.quit_driver") as m_quit,
        patch("app.rpa.bot.perform_login") as m_login,
        patch("app.rpa.bot.go_to_generar_factura") as m_nav,
        patch("app.rpa.bot.apply_filters_and_search") as m_filter,
        patch("app.rpa.bot.extract_table_rows", return_value=rows) as m_extract,
    ):
        if set_running_error:
            m_running.side_effect = set_running_error
        if login_error:
            m_login.side_effect = login_error
        if nav_error:
            m_nav.side_effect = nav_error
        if filter_error:
            m_filter.side_effect = filter_error
        if extract_error:
            m_extract.side_effect = extract_error
        if persist_error:
            m_persist.side_effect = persist_error

        run_extraction_job(JOB_ID, FECHA_INICIAL, FECHA_FINAL, LIMIT)

        return {
            "running": m_running,
            "persist": m_persist,
            "success": m_success,
            "failed": m_failed,
            "create_driver": m_create_driver,
            "quit_driver": m_quit,
            "login": m_login,
            "nav": m_nav,
            "filter": m_filter,
            "extract": m_extract,
        }


# ── Happy path ────────────────────────────────────────────────────────────────


class TestHappyPath:
    def test_status_transitions_in_order(self) -> None:
        """running must be called before success; failed must not be called."""
        mocks = _run()
        mocks["running"].assert_called_once()
        mocks["success"].assert_called_once()
        mocks["failed"].assert_not_called()

    def test_success_receives_correct_row_count(self) -> None:
        mocks = _run(rows=SAMPLE_ROWS)
        job_id_arg, count_arg = mocks["success"].call_args.args
        assert count_arg == len(SAMPLE_ROWS)

    def test_persist_called_before_success(self) -> None:
        """Records must be in the DB before the job is marked complete."""
        call_order: list[str] = []

        async def fake_persist(*_):
            call_order.append("persist")

        async def fake_success(*_):
            call_order.append("success")

        with (
            patch("app.rpa.bot._set_running", new_callable=AsyncMock),
            patch("app.rpa.bot._persist", side_effect=fake_persist),
            patch("app.rpa.bot._set_success", side_effect=fake_success),
            patch("app.rpa.bot._set_failed", new_callable=AsyncMock),
            patch("app.rpa.bot.create_driver"),
            patch("app.rpa.bot.quit_driver"),
            patch("app.rpa.bot.perform_login"),
            patch("app.rpa.bot.go_to_generar_factura"),
            patch("app.rpa.bot.apply_filters_and_search"),
            patch("app.rpa.bot.extract_table_rows", return_value=SAMPLE_ROWS),
        ):
            run_extraction_job(JOB_ID, FECHA_INICIAL, FECHA_FINAL, LIMIT)

        assert call_order == ["persist", "success"]

    def test_persist_receives_job_id_and_rows(self) -> None:
        mocks = _run(rows=SAMPLE_ROWS)
        job_id_arg, rows_arg = mocks["persist"].call_args.args
        assert str(job_id_arg) == JOB_ID
        assert rows_arg == SAMPLE_ROWS

    def test_browser_is_always_quit(self) -> None:
        mocks = _run()
        mocks["quit_driver"].assert_called_once()

    def test_all_rpa_steps_are_called(self) -> None:
        mocks = _run()
        mocks["login"].assert_called_once()
        mocks["nav"].assert_called_once()
        mocks["filter"].assert_called_once()
        mocks["extract"].assert_called_once()

    def test_extract_receives_limit(self) -> None:
        mocks = _run()
        _, limit_arg = mocks["extract"].call_args.args
        assert limit_arg == LIMIT

    def test_zero_rows_marks_success_with_zero(self) -> None:
        mocks = _run(rows=[])
        mocks["success"].assert_called_once()
        _, count_arg = mocks["success"].call_args.args
        assert count_arg == 0
        mocks["failed"].assert_not_called()


# ── Known RPA errors → failed ─────────────────────────────────────────────────


class TestKnownRpaErrors:
    @pytest.mark.parametrize(
        "error_kwarg, exc_type",
        [
            ("login_error", LoginError("bad credentials")),
            ("nav_error", NavigationError("menu not found")),
            ("filter_error", FilterError("date input timeout")),
            ("extract_error", ExtractionError("table selector wrong")),
        ],
    )
    def test_marks_failed_with_error_message(self, error_kwarg, exc_type) -> None:
        mocks = _run(**{error_kwarg: exc_type})
        mocks["failed"].assert_called_once()
        _, error_arg = mocks["failed"].call_args.args
        assert type(exc_type).__name__ in error_arg
        mocks["success"].assert_not_called()

    def test_browser_quit_even_on_login_error(self) -> None:
        mocks = _run(login_error=LoginError("timeout"))
        mocks["quit_driver"].assert_called_once()

    def test_persist_not_called_on_nav_error(self) -> None:
        mocks = _run(nav_error=NavigationError("submenu missing"))
        mocks["persist"].assert_not_called()


# ── Unexpected errors → failed ────────────────────────────────────────────────


class TestUnexpectedErrors:
    def test_unexpected_exception_marks_failed(self) -> None:
        mocks = _run(login_error=RuntimeError("segfault simulation"))
        mocks["failed"].assert_called_once()
        mocks["success"].assert_not_called()

    def test_browser_quit_on_unexpected_error(self) -> None:
        mocks = _run(nav_error=RuntimeError("oops"))
        mocks["quit_driver"].assert_called_once()

    def test_persist_error_marks_failed(self) -> None:
        """A DB failure during persist should mark the job as failed."""
        mocks = _run(persist_error=RuntimeError("DB connection lost"))
        mocks["failed"].assert_called_once()
        mocks["success"].assert_not_called()


# ── DB failure before start ───────────────────────────────────────────────────


class TestDbFailureBeforeStart:
    def test_set_running_failure_calls_set_failed(self) -> None:
        """`_set_running` failing must still attempt to mark the job as failed."""
        mocks = _run(set_running_error=RuntimeError("DB not ready"))
        mocks["failed"].assert_called_once()

    def test_set_running_failure_does_not_open_browser(self) -> None:
        """If the DB is down before we start, no browser session should open."""
        mocks = _run(set_running_error=RuntimeError("DB not ready"))
        mocks["create_driver"].assert_not_called()
        mocks["quit_driver"].assert_not_called()

    def test_set_running_failure_does_not_call_success(self) -> None:
        mocks = _run(set_running_error=RuntimeError("DB not ready"))
        mocks["success"].assert_not_called()
