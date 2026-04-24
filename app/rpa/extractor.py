"""
Table row extraction — Aquila "Generar Factura" table (id="detalle_consulta").

Key Aquila-specific notes
─────────────────────────
1. Authorization code: rendered as a hidden <input class="codigoAut" value="…">
   inside column 7.  cell.text returns "".  Must use get_attribute("value").

2. Date format: Aquila renders "YYYY-MM-DD HH:MM:SS".  date.fromisoformat()
   rejects the time component.  Some rows have comma-separated dates when an
   order spans multiple days.  _clean_date() normalises both cases.

3. DataTables child rows: when a row is expanded the portal inserts a sibling
   <tr class="child"> with a completely different structure.  These are already
   excluded by the BODY_ROWS selector in selectors.py.

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
    skipped = 0

    for idx, row_el in enumerate(all_rows):
        if len(extracted) >= limit_requested:
            logger.debug(
                "extractor_limit_reached",
                collected=len(extracted),
                limit_requested=limit_requested,
            )
            break

        row_data = parse_row(row_el, row_index=idx)

        if not row_data:
            skipped += 1
            logger.debug("extractor_skipped_empty_row", row_index=idx)
            continue

        extracted.append(row_data)

    logger.info(
        "extractor_complete",
        collected=len(extracted),
        skipped=skipped,
        total_available=total_available,
        limit_requested=limit_requested,
    )
    return extracted


def parse_row(row_el: WebElement, row_index: int = -1) -> dict:
    """
    Parse a single <tr> element into a dict.

    Always stores every cell under a positional key ("col_0" … "col_N") so no
    data is lost.  Also extracts named fields for the Record model and extra
    Aquila-specific fields (authorization_code, cups, modality, status).

    Returns an empty dict if all cells are blank (caller should skip the row).
    """
    cells = row_el.find_elements(By.TAG_NAME, "td")

    if not cells:
        logger.debug("extractor_row_no_cells", row_index=row_index)
        return {}

    # Positional capture — always present, drives raw_row_json.
    # Use textContent (not .text) so that cells with style="display:none" are included.
    positional: dict[str, str] = {
        f"col_{i}": (cell.get_attribute("textContent") or "").strip()
        for i, cell in enumerate(cells)
    }

    # If every cell is blank this is a filler/separator row — discard it
    if not any(positional.values()):
        return {}

    # Named capture — Aquila-verified fields
    named = _extract_named_columns(cells, row_el)

    logger.debug(
        "extractor_row_parsed",
        row_index=row_index,
        cell_count=len(cells),
        order=named.get("external_row_id"),
        document=named.get("patient_document"),
        patient=named.get("patient_name"),
        auth_code=named.get("authorization_code"),
        date=named.get("date_service_or_facturation"),
        site=named.get("site"),
        cups=named.get("cups"),
        modality=named.get("modality"),
        status=named.get("aquila_status"),
    )

    return {**positional, **named}


def _clean_date(raw: str | None) -> str | None:
    """
    Normalise an Aquila date cell value to "YYYY-MM-DD".

    Aquila renders dates as ``"YYYY-MM-DD HH:MM:SS"`` and sometimes as
    comma-separated values when an order spans multiple days
    (``"2026-03-08 00:00:00, 2026-03-09 00:00:00"``).  Only the first date
    and only the date part are kept so that record_service._parse_date()
    can call date.fromisoformat() successfully.
    """
    if not raw:
        return None
    first = raw.split(",")[0].strip()
    date_part = first.split(" ")[0].strip()
    return date_part or None


def _extract_named_columns(cells: list[WebElement], row_el: WebElement) -> dict:
    """
    Populate named columns from verified Aquila cell positions.

    Special cases handled here:
    - authorization_code: hidden <input class="codigoAut" value="…"> — not cell text.
    - external_row_id (order number): may contain trailing text; only first token kept.
    - date_service_or_facturation: normalised from "YYYY-MM-DD HH:MM:SS" → "YYYY-MM-DD".
    """
    named: dict[str, str | None] = {}

    def _get(index: int | None) -> str | None:
        if index is None or index >= len(cells):
            return None
        # Use textContent so hidden cells (display:none) return their content.
        return (cells[index].get_attribute("textContent") or "").strip() or None

    # ── Authorization code ────────────────────────────────────────────────────
    # Stored in a hidden <input class="codigoAut" value="…"> inside the cell.
    # cells[7].text is always "" — must use get_attribute("value").
    auth_els = row_el.find_elements(By.CLASS_NAME, ColumnIndex.AUTHORIZATION_CODE_INPUT_CLASS)
    if auth_els:
        raw_auth = auth_els[0].get_attribute("value") or ""
        named["authorization_code"] = raw_auth.strip() or None
    else:
        logger.warning(
            "extractor_auth_input_not_found",
            hint=f"No <input class='{ColumnIndex.AUTHORIZATION_CODE_INPUT_CLASS}'> in row — "
                 "column layout may have changed",
        )

    # ── Order number (external_row_id) ─────────────────────────────────────────
    # Aquila may append extra text; take only the first whitespace-delimited token.
    if ColumnIndex.EXTERNAL_ROW_ID is not None:
        raw_order = _get(ColumnIndex.EXTERNAL_ROW_ID)
        named["external_row_id"] = raw_order.split()[0] if raw_order else None

    # ── Patient info ──────────────────────────────────────────────────────────
    if ColumnIndex.PATIENT_NAME is not None:
        named["patient_name"] = _get(ColumnIndex.PATIENT_NAME)

    if ColumnIndex.PATIENT_DOCUMENT is not None:
        named["patient_document"] = _get(ColumnIndex.PATIENT_DOCUMENT)

    # ── Date ──────────────────────────────────────────────────────────────────
    if ColumnIndex.DATE_SERVICE_OR_FACTURATION is not None:
        named["date_service_or_facturation"] = _clean_date(_get(ColumnIndex.DATE_SERVICE_OR_FACTURATION))

    # ── Site ──────────────────────────────────────────────────────────────────
    if ColumnIndex.SITE is not None:
        named["site"] = _get(ColumnIndex.SITE)

    # ── Contract ──────────────────────────────────────────────────────────────
    if ColumnIndex.CONTRACT is not None:
        named["contract"] = _get(ColumnIndex.CONTRACT)

    # ── Extra Aquila fields (stored in raw_row_json) ──────────────────────────
    if ColumnIndex.CUPS is not None:
        named["cups"] = _get(ColumnIndex.CUPS)

    if ColumnIndex.MODALITY is not None:
        named["modality"] = _get(ColumnIndex.MODALITY)

    if ColumnIndex.STATUS is not None:
        named["aquila_status"] = _get(ColumnIndex.STATUS)

    return named
