"""
Unit tests for the RPA extractor and filter modules.
All Selenium interactions are mocked — no browser or grid is started.
"""

from datetime import date
from unittest.mock import MagicMock

from app.rpa.extractor import extract_table_rows, parse_row
from app.rpa.filters import _fill_date_input
from app.rpa.selectors import PORTAL_DATE_FORMAT, ColumnIndex

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_cell(text: str) -> MagicMock:
    cell = MagicMock()
    cell.text = text
    cell.get_attribute.return_value = text
    return cell


def _make_row_el(cell_texts: list[str]) -> MagicMock:
    row = MagicMock()
    row.find_elements.return_value = [_make_cell(t) for t in cell_texts]
    return row


# ── selectors.py ──────────────────────────────────────────────────────────────


class TestPortalDateFormat:
    def test_format_string_is_set(self) -> None:
        assert PORTAL_DATE_FORMAT, "PORTAL_DATE_FORMAT must not be empty"

    def test_formats_a_date(self) -> None:
        formatted = date(2024, 3, 15).strftime(PORTAL_DATE_FORMAT)
        assert "2024" in formatted or "15" in formatted or "03" in formatted


# ── extractor.parse_row ───────────────────────────────────────────────────────


class TestParseRow:
    def test_returns_positional_keys(self) -> None:
        row = _make_row_el(["Alice", "12345678", "2024-01-01"])
        result = parse_row(row)
        assert result["col_0"] == "Alice"
        assert result["col_1"] == "12345678"
        assert result["col_2"] == "2024-01-01"

    def test_strips_whitespace(self) -> None:
        row = _make_row_el(["  padded  "])
        result = parse_row(row)
        assert result["col_0"] == "padded"

    def test_empty_row_returns_empty_dict(self) -> None:
        row = _make_row_el([])
        assert parse_row(row) == {}

    def test_all_blank_cells_returns_empty_dict(self) -> None:
        row = _make_row_el(["", "  ", ""])
        assert parse_row(row) == {}

    def test_named_columns_populated_when_index_set(self) -> None:
        """Once ColumnIndex is configured, named keys appear in the output."""
        row = _make_row_el(
            ["INV-001", "Carlos López", "87654321", "2024-05-01", "Sede Norte", "EPS A"]
        )

        # Temporarily configure ColumnIndex for this test
        original = {
            "EXTERNAL_ROW_ID": ColumnIndex.EXTERNAL_ROW_ID,
            "PATIENT_NAME": ColumnIndex.PATIENT_NAME,
            "PATIENT_DOCUMENT": ColumnIndex.PATIENT_DOCUMENT,
            "DATE_SERVICE_OR_FACTURATION": ColumnIndex.DATE_SERVICE_OR_FACTURATION,
            "SITE": ColumnIndex.SITE,
            "CONTRACT": ColumnIndex.CONTRACT,
        }
        try:
            ColumnIndex.EXTERNAL_ROW_ID = 0
            ColumnIndex.PATIENT_NAME = 1
            ColumnIndex.PATIENT_DOCUMENT = 2
            ColumnIndex.DATE_SERVICE_OR_FACTURATION = 3
            ColumnIndex.SITE = 4
            ColumnIndex.CONTRACT = 5

            result = parse_row(row)
            assert result["external_row_id"] == "INV-001"
            assert result["patient_name"] == "Carlos López"
            assert result["patient_document"] == "87654321"
            assert result["date_service_or_facturation"] == "2024-05-01"
            assert result["site"] == "Sede Norte"
            assert result["contract"] == "EPS A"
            # Positional keys still present
            assert "col_0" in result
        finally:
            for attr, val in original.items():
                setattr(ColumnIndex, attr, val)


# ── extractor.extract_table_rows ─────────────────────────────────────────────


class TestExtractTableRows:
    def test_respects_limit(self) -> None:
        driver = MagicMock()
        rows = [_make_row_el([f"val{i}"]) for i in range(10)]
        driver.find_elements.return_value = rows

        result = extract_table_rows(driver, limit_requested=3)
        assert len(result) == 3

    def test_limit_larger_than_available(self) -> None:
        driver = MagicMock()
        driver.find_elements.return_value = [_make_row_el([f"val{i}"]) for i in range(2)]
        assert len(extract_table_rows(driver, limit_requested=100)) == 2

    def test_empty_table_returns_empty_list(self) -> None:
        driver = MagicMock()
        driver.find_elements.return_value = []
        assert extract_table_rows(driver, limit_requested=10) == []

    def test_each_result_is_a_dict(self) -> None:
        driver = MagicMock()
        driver.find_elements.return_value = [_make_row_el(["Alice", "doc123"])]
        result = extract_table_rows(driver, limit_requested=10)
        assert isinstance(result[0], dict)

    def test_blank_rows_are_skipped(self) -> None:
        driver = MagicMock()
        blank = _make_row_el(["", "  "])
        real = _make_row_el(["data"])
        driver.find_elements.return_value = [blank, real, blank]
        result = extract_table_rows(driver, limit_requested=10)
        assert len(result) == 1
        assert result[0]["col_0"] == "data"


# ── filters._fill_date_input ──────────────────────────────────────────────────


class TestFillDateInput:
    def test_sets_value_via_js_and_tabs_out(self) -> None:
        driver = MagicMock()
        element = MagicMock()
        _fill_date_input(driver, element, "15/01/2024")

        # Value is written through JavaScript, not via send_keys
        assert driver.execute_script.call_count == 2
        first_call_args = driver.execute_script.call_args_list[0][0]
        assert element in first_call_args
        assert "15/01/2024" in first_call_args

        # TAB closes the jQuery UI calendar popup
        from selenium.webdriver.common.keys import Keys
        element.send_keys.assert_called_once_with(Keys.TAB)
