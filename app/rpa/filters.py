"""
Date filter application and search result detection.

Responsibilities:
  1. Fill the fecha_inicial and fecha_final inputs.
  2. Click the Buscar button.
  3. Wait for the results table to change state (updated rows OR no-results message).

All selectors are imported from selectors.py — do not add locators here.

NOTE ON DATE INPUTS
───────────────────
Some portals render custom date pickers (React DatePicker, Flatpickr, etc.)
that do not respond to send_keys.  In that case, use the JavaScript fallback
documented in _fill_date_input() below.
"""

import time
from datetime import date

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.rpa.selectors import PORTAL_DATE_FORMAT, FilterForm, ResultTable

_SHORT_WAIT_S = 5   # seconds to wait for dropdown to open / close


logger = get_logger(__name__)

_POLL_INTERVAL_S = 0.5


class FilterError(Exception):
    """Raised when filters cannot be applied or results do not load."""


def apply_filters_and_search(
    driver: WebDriver,
    fecha_inicial: date,
    fecha_final: date,
    settings: Settings | None = None,
) -> None:
    """
    Fill the date range inputs, click Buscar, and wait for results to load.

    Raises:
        FilterError: on timeout at any step.
    """
    if settings is None:
        settings = get_settings()

    timeout = settings.selenium_timeout_seconds
    wait = WebDriverWait(driver, timeout)

    fi_str = fecha_inicial.strftime(PORTAL_DATE_FORMAT)
    ff_str = fecha_final.strftime(PORTAL_DATE_FORMAT)

    logger.info(
        "filters_start",
        fecha_inicial=fi_str,
        fecha_final=ff_str,
    )

    try:
        # ── Step 1: Contratos — disabled by portal (user's contract is fixed) ──
        # Only interact if the dropdown is actually enabled; skip silently if not.
        _bootstrap_select_all(driver, wait, FilterForm.CONTRATOS_TRIGGER, "contratos")

        # ── Step 2: select all Sedes ──────────────────────────────────────────
        _bootstrap_select_all(driver, wait, FilterForm.SEDES_TRIGGER, "sedes")

        # ── Step 3: fill fecha_inicial ────────────────────────────────────────
        fi_el = wait.until(
            EC.element_to_be_clickable(FilterForm.FECHA_INICIAL),
            message=f"fecha_inicial input not clickable after {timeout}s",
        )
        _fill_date_input(driver, fi_el, fi_str)
        logger.debug("filters_fecha_inicial_set", value=fi_str)

        # ── Step 4: fill fecha_final ──────────────────────────────────────────
        ff_el = wait.until(
            EC.element_to_be_clickable(FilterForm.FECHA_FINAL),
            message=f"fecha_final input not clickable after {timeout}s",
        )
        _fill_date_input(driver, ff_el, ff_str)
        logger.debug("filters_fecha_final_set", value=ff_str)

        # ── Step 5: snapshot tbody reference for staleness detection ─────────
        # DataTables rebuilds the <tbody> element on every search — even when
        # the result is 0 rows.  Capturing a stale reference here lets us wait
        # for the actual AJAX round-trip to complete instead of reading the
        # pre-existing empty state.
        try:
            pre_tbody = driver.find_element(
                By.CSS_SELECTOR, "#detalle_consulta tbody"
            )
        except Exception:
            pre_tbody = None
        pre_search_rows = _count_table_rows(driver)
        logger.debug("filters_pre_search_row_count", count=pre_search_rows)

        # ── Step 6: click Buscar ──────────────────────────────────────────────
        buscar = wait.until(
            EC.element_to_be_clickable(FilterForm.BUSCAR_BUTTON),
            message=f"Buscar button not clickable after {timeout}s",
        )
        buscar.click()
        logger.info("filters_buscar_clicked")

        # ── Step 7: wait for AJAX + results ───────────────────────────────────
        _wait_for_results(driver, pre_search_rows, timeout, pre_tbody)

    except TimeoutException as exc:
        logger.error("filters_timeout", current_url=driver.current_url, detail=str(exc))
        raise FilterError(
            f"Timed out while applying filters or waiting for results: {exc}. "
            "Verify selectors in selectors.py → FilterForm / ResultTable."
        ) from exc


# ── Helpers ───────────────────────────────────────────────────────────────────


def _bootstrap_select_all(
    driver: WebDriver,
    wait: WebDriverWait,
    trigger_locator: tuple,
    label: str,
) -> None:
    """
    Open a Bootstrap Select dropdown and select all available options.

    Two variants handled automatically:

    A) Dropdown with actionsBox (e.g. Sedes):  has <button class="bs-select-all">.
    B) Dropdown without actionsBox (e.g. Contratos):  click each unselected <li>.

    Disabled / pre-selected detection:
    - Instead of reading the "disabled" CSS class (which can be unreliable),
      we click the trigger and then check whether a .dropdown-menu.open
      element actually appeared.  If it did not open, the dropdown is either
      disabled or pre-selected by the portal — we log and skip gracefully.

    Does NOT raise on failure — logs details and continues so Buscar still runs.
    """
    try:
        trigger = wait.until(
            EC.presence_of_element_located(trigger_locator),
            message=f"{label} dropdown trigger not present",
        )

        # Log raw element state for easier future debugging.
        elem_class = trigger.get_attribute("class") or ""
        elem_disabled_attr = trigger.get_attribute("disabled")
        logger.debug(
            "filters_dropdown_trigger_found",
            label=label,
            class_attr=elem_class,
            disabled_attr=elem_disabled_attr,
            is_enabled=trigger.is_enabled(),
        )

        # Try clicking the trigger.
        try:
            trigger.click()
        except Exception:
            driver.execute_script("arguments[0].click();", trigger)

        # Give the dropdown a moment to open.
        time.sleep(0.4)

        # Check whether the dropdown actually opened (Bootstrap Select adds
        # the class "open" to the parent or uses .dropdown-menu.open).
        open_menus = driver.find_elements(By.CSS_SELECTOR, ".dropdown-menu.open")
        if not open_menus:
            logger.info(
                "filters_dropdown_did_not_open",
                label=label,
                hint="dropdown may be disabled or already fully pre-selected by portal",
            )
            return

        logger.debug("filters_dropdown_opened", label=label)

        # ── Variant A: "Select All" button present ─────────────────────────
        select_all_btns = driver.find_elements(*FilterForm.SELECT_ALL_BUTTON)
        visible_select_all = [b for b in select_all_btns if b.is_displayed()]
        if visible_select_all:
            visible_select_all[0].click()
            logger.debug("filters_select_all_clicked", label=label)
        else:
            # ── Variant B: click every unselected option individually ───────
            opts = driver.find_elements(
                By.CSS_SELECTOR,
                ".dropdown-menu.open .dropdown-menu.inner li:not(.selected) a",
            )
            clicked = 0
            for opt in opts:
                if opt.is_displayed():
                    opt.click()
                    clicked += 1
            logger.debug("filters_options_clicked", label=label, count=clicked)

        # Close the dropdown by pressing Escape or clicking the trigger again.
        trigger.click()
        time.sleep(0.2)
        logger.info("filters_dropdown_all_selected", label=label)

    except TimeoutException:
        logger.warning(
            "filters_dropdown_select_all_failed",
            label=label,
            hint="Verify FilterForm trigger selectors in selectors.py",
        )


def _fill_date_input(driver: WebDriver, element: WebElement, value: str) -> None:
    """
    Write a date string into a jQuery UI datepicker input.

    jQuery datepicker opens a calendar popup on focus.  The strategy is:
      1. Set the value via JavaScript (bypasses the popup entirely).
      2. Fire 'change' so jQuery datepicker registers the new date internally.
      3. Press Tab to dismiss any open popup and move focus, preventing
         the popup from intercepting the next element interaction.
    """
    driver.execute_script("arguments[0].value = arguments[1];", element, value)
    driver.execute_script(
        "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
        element,
    )
    element.send_keys(Keys.TAB)


def _count_table_rows(driver: WebDriver) -> int:
    return len(driver.find_elements(*ResultTable.BODY_ROWS))


def _wait_for_results(
    driver: WebDriver,
    previous_row_count: int,
    timeout: int,
    pre_tbody: WebElement | None = None,
) -> None:
    """
    Wait until the DataTables search AJAX round-trip is complete.

    VERIFIED table: id="detalle_consulta" (DataTables, responsive mode).

    Strategy
    ────────
    1. Staleness of pre_tbody — DataTables replaces the <tbody> element on
       every render, including the "0 results" case.  This is the most reliable
       signal that the AJAX response has been processed.  If pre_tbody is None
       (page had no tbody before Buscar), skip this step.

    2. Polling for outcome — once staleness is detected (or after a minimum
       wait), check:
         B) td.dataTables_empty visible  → search returned 0 rows.
         C) row count differs from snapshot → rows loaded.

    3. Graceful fallback — if staleness never fires but the timeout is reached,
       log a warning and return so Buscar is not retried.
    """
    logger.debug("filters_waiting_for_results", previous_row_count=previous_row_count)

    # ── Step 1: wait for tbody to become stale ────────────────────────────────
    if pre_tbody is not None:
        try:
            WebDriverWait(driver, timeout).until(
                EC.staleness_of(pre_tbody),
                message="DataTables tbody did not become stale — AJAX may not have fired",
            )
            logger.debug("filters_tbody_became_stale")
        except TimeoutException:
            logger.warning(
                "filters_tbody_staleness_timeout",
                hint="DataTables did not rebuild tbody within timeout",
            )

    # ── Step 2: poll for actual outcome (up to 10 s after stale) ─────────────
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        # Condition B: "Tabla sin información" cell
        no_results = driver.find_elements(*ResultTable.NO_RESULTS_MESSAGE)
        if no_results and no_results[0].is_displayed():
            logger.info("filters_search_returned_no_results")
            return

        # Condition C: real data rows appeared
        current_count = _count_table_rows(driver)
        if current_count != previous_row_count:
            logger.info(
                "filters_results_loaded",
                previous_count=previous_row_count,
                new_count=current_count,
            )
            return

        time.sleep(_POLL_INTERVAL_S)

    # Graceful fallback — neither condition fired within 10 s after AJAX.
    # Continue anyway; the extractor will simply find 0 rows.
    logger.warning(
        "filters_results_ambiguous",
        row_count=_count_table_rows(driver),
        hint="Neither empty-state cell nor data rows detected after AJAX; "
             "check ResultTable selectors in selectors.py",
    )
