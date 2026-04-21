"""
Table row extraction.

Responsibilities:
  1. Locate all result rows visible in the DOM.
  2. Parse each row into a dict.
  3. Stop once `limit_requested` rows have been collected.

Column mapping
──────────────
Until ColumnIndex values in selectors.py are verified against the real DOM,
parse_row() stores every cell under a positional key ("col_0", "col_1", …)
and returns that full dict as raw_row_json.  Named columns in the Record model
will be NULL until ColumnIndex is filled in.

Once you have confirmed the column positions:
  1. Set ColumnIndex.PATIENT_NAME = <actual index>, etc. in selectors.py.
  2. No changes needed here — parse_row() reads ColumnIndex at call time.

All selectors are imported from selectors.py — do not add locators here.
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from app.core.logging import get_logger
from app.rpa.selectors import ColumnIndex, ResultTable

logger = get_logger(__name__)


class ExtractionError(Exception):
    """Raised when the extraction step fails unrecoverably."""


def extract_table_rows(driver: WebDriver, limit_requested: int) -> list[dict]:
    """
    Collect up to `limit_requested` rows from the visible results table.

    Returns a list of dicts.  Each dict will always contain all positional
    keys ("col_0" … "col_N") and, once ColumnIndex is configured, will also
    contain the named keys expected by record_service.create_records():
      external_row_id, patient_name, patient_document,
      date_service_or_facturation, site, contract

    Empty rows (all cells blank) are skipped.
    """
    all_rows = driver.find_elements(*ResultTable.BODY_ROWS)
    total_available = len(all_rows)

    logger.info(
        "extractor_rows_found",
        total_in_dom=total_available,
        limit_requested=limit_requested,
    )

    extracted: list[dict] = []

    for row_el in all_rows:
        if len(extracted) >= limit_requested:
            logger.debug(
                "extractor_limit_reached",
                collected=len(extracted),
                limit_requested=limit_requested,
            )
            break

        row_data = parse_row(row_el)

        if not row_data:
            logger.debug("extractor_skipped_empty_row")
            continue

        extracted.append(row_data)

    logger.info(
        "extractor_complete",
        collected=len(extracted),
        total_available=total_available,
        limit_requested=limit_requested,
    )
    return extracted


def parse_row(row_el: WebElement) -> dict:
    """
    Parse a single <tr> element into a dict.

    The dict always contains positional keys ("col_0" … "col_N") so that no
    data is ever lost.  When ColumnIndex values are set (not None), it also
    adds the named keys that map directly to Record model columns.

    Returns an empty dict if all cells are blank (caller should skip the row).
    """
    cells = row_el.find_elements(By.TAG_NAME, "td")

    if not cells:
        return {}

    # Positional capture — always present, drives raw_row_json
    positional: dict[str, str] = {f"col_{i}": cell.text.strip() for i, cell in enumerate(cells)}

    # If every cell is blank this is a filler/separator row — discard it
    if not any(positional.values()):
        return {}

    # Named capture — only active once ColumnIndex has been verified
    named = _extract_named_columns(cells)

    return {**positional, **named}


def _extract_named_columns(cells: list[WebElement]) -> dict:
    """
    Attempt to populate named Record columns from verified cell positions.

    Returns an empty dict if ColumnIndex has not been configured yet
    (all attributes are None), so the caller's dict only contains positional keys.
    """
    named: dict[str, str | None] = {}

    def _get(index: int | None) -> str | None:
        if index is None or index >= len(cells):
            return None
        return cells[index].text.strip() or None

    if ColumnIndex.EXTERNAL_ROW_ID is not None:
        named["external_row_id"] = _get(ColumnIndex.EXTERNAL_ROW_ID)

    if ColumnIndex.PATIENT_NAME is not None:
        named["patient_name"] = _get(ColumnIndex.PATIENT_NAME)

    if ColumnIndex.PATIENT_DOCUMENT is not None:
        named["patient_document"] = _get(ColumnIndex.PATIENT_DOCUMENT)

    if ColumnIndex.DATE_SERVICE_OR_FACTURATION is not None:
        named["date_service_or_facturation"] = _get(ColumnIndex.DATE_SERVICE_OR_FACTURATION)

    if ColumnIndex.SITE is not None:
        named["site"] = _get(ColumnIndex.SITE)

    if ColumnIndex.CONTRACT is not None:
        named["contract"] = _get(ColumnIndex.CONTRACT)

    return named
