"""
Filter application — Facturación → Generar Factura form.

Required filter order (VERIFIED from PDX-RPA-SaviaSalud reference project):
  1. Convenio  → "Savia Salud Subsidiado"  (unlocks Contrato via AJAX)
  2. Contrato  → "SAVIA SALUD SUBSIDIADO"  (unlocks Sedes via AJAX)
  3. Sedes     → select all
  4. Modalidad → settings.portal_modalidad (default: "US")
  5. Fecha inicial / Fecha final
  6. Buscar → wait for DataTables to update

Between each dropdown selection the portal fires an AJAX request and renders
a BlockUI overlay.  _wait_for_blockui() must be called before every interaction
to avoid ElementClickInterceptedException on overlapping elements.
"""

import time
from datetime import date

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.rpa.selectors import PORTAL_DATE_FORMAT, FilterForm, ResultTable

logger = get_logger(__name__)

_POLL_INTERVAL_S = 0.5
_DROPDOWN_PAUSE_S = 0.5  # time after clicking trigger before checking .open


class FilterError(Exception):
    """Raised when filters cannot be applied or results do not load."""


def apply_filters_and_search(
    driver: WebDriver,
    fecha_inicial: date,
    fecha_final: date,
    settings: Settings | None = None,
) -> None:
    """
    Apply all required filters and click Buscar.

    Filter order is critical (each step unlocks the next via AJAX):
      1. Convenio  → unlocks Contrato
      2. Contrato  → unlocks Sedes
      3. Sedes     → select all
      4. Modalidad
      5. Dates
      6. Buscar

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
        convenio=settings.portal_convenio,
        modalidad=settings.portal_modalidad,
    )

    try:
        # ── Step 1: Convenio ──────────────────────────────────────────────────
        _wait_for_blockui(driver, timeout)
        _select_option(
            driver, wait, timeout,
            FilterForm.CONVENIOS_TRIGGER,
            settings.portal_convenio,
            "convenio",
        )

        # ── Step 2: Contrato (enabled by Convenio AJAX) ───────────────────────
        _wait_for_blockui(driver, timeout)
        _select_option(
            driver, wait, timeout,
            FilterForm.CONTRATOS_TRIGGER,
            settings.portal_contrato,
            "contrato",
        )

        # ── Step 3: Sedes — select all (enabled by Contrato AJAX) ─────────────
        _wait_for_blockui(driver, timeout)
        _select_all_options(driver, wait, timeout, FilterForm.SEDES_TRIGGER, "sedes")

        # ── Step 4: Modalidad ─────────────────────────────────────────────────
        _wait_for_blockui(driver, timeout)
        _select_option(
            driver, wait, timeout,
            FilterForm.MODALIDADES_TRIGGER,
            settings.portal_modalidad,
            "modalidad",
        )

        # ── Step 5: Fecha inicial ─────────────────────────────────────────────
        fi_el = wait.until(
            EC.element_to_be_clickable(FilterForm.FECHA_INICIAL),
            message=f"fecha_inicial not clickable after {timeout}s",
        )
        _fill_date_input(driver, fi_el, fi_str)
        logger.debug("filters_fecha_inicial_set", value=fi_str)

        # ── Step 6: Fecha final ───────────────────────────────────────────────
        ff_el = wait.until(
            EC.element_to_be_clickable(FilterForm.FECHA_FINAL),
            message=f"fecha_final not clickable after {timeout}s",
        )
        _fill_date_input(driver, ff_el, ff_str)
        logger.debug("filters_fecha_final_set", value=ff_str)

        # ── Snapshot tbody before Buscar for staleness detection ──────────────
        try:
            pre_tbody = driver.find_element(By.CSS_SELECTOR, "#detalle_consulta tbody")
        except Exception:
            pre_tbody = None
        pre_count = _count_table_rows(driver)
        logger.debug("filters_pre_search_row_count", count=pre_count)

        # ── Step 7: click Buscar ──────────────────────────────────────────────
        _wait_for_blockui(driver, timeout)
        buscar = wait.until(
            EC.element_to_be_clickable(FilterForm.BUSCAR_BUTTON),
            message=f"Buscar button not clickable after {timeout}s",
        )
        buscar.click()
        logger.info("filters_buscar_clicked")

        # Fixed pause: lets DataTables fire its AJAX request before polling.
        time.sleep(1.5)

        # ── Step 8: wait for DataTables AJAX to complete ──────────────────────
        _wait_for_results(driver, pre_count, timeout, pre_tbody)

    except TimeoutException as exc:
        logger.error("filters_timeout", current_url=driver.current_url, detail=str(exc))
        raise FilterError(
            f"Timed out while applying filters: {exc}. "
            "Verify FilterForm selectors in selectors.py."
        ) from exc


# ── Helpers ───────────────────────────────────────────────────────────────────


def _wait_for_blockui(driver: WebDriver, timeout: int) -> None:
    """Wait until the BlockUI loading overlay disappears."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located(FilterForm.BLOCKUI_OVERLAY)
        )
    except TimeoutException:
        pass  # no overlay present — safe to proceed


def _wait_for_enabled(
    driver: WebDriver,
    timeout: int,
    trigger_locator: tuple,
    label: str,
) -> WebElement | None:
    """
    Wait until the Bootstrap Select trigger no longer carries the 'disabled' class.
    Returns the trigger element, or None if it remained disabled.
    """
    def _not_disabled(d: WebDriver) -> WebElement | bool:
        els = d.find_elements(*trigger_locator)
        if not els:
            return False
        el = els[0]
        if "disabled" in (el.get_attribute("class") or "").split():
            return False
        return el

    try:
        trigger = WebDriverWait(driver, timeout).until(
            _not_disabled,
            message=f"{label} trigger did not become enabled within {timeout}s",
        )
        logger.debug("filters_dropdown_enabled", label=label)
        return trigger
    except TimeoutException:
        logger.warning(
            "filters_dropdown_still_disabled",
            label=label,
            hint="Proceeding anyway — previous AJAX step may have failed",
        )
        return None


def _select_option(
    driver: WebDriver,
    wait: WebDriverWait,
    timeout: int,
    trigger_locator: tuple,
    option_text: str,
    label: str,
) -> None:
    """
    Open a Bootstrap Select dropdown and click the option matching option_text.
    Waits for the trigger to become enabled before interacting.
    """
    trigger = _wait_for_enabled(driver, timeout, trigger_locator, label)
    if trigger is None:
        return  # already warned

    # Open dropdown.
    try:
        trigger.click()
    except Exception:
        driver.execute_script("arguments[0].click();", trigger)
    time.sleep(_DROPDOWN_PAUSE_S)

    # Find and click the matching option.
    option_xpath = (
        ".//ul[contains(@class,'dropdown-menu')]"
        f"//span[normalize-space(text())='{option_text}']"
    )
    try:
        option = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, option_xpath)),
            message=f"Option '{option_text}' not visible in {label} dropdown",
        )
        option.click()
        logger.info("filters_option_selected", label=label, option=option_text)
    except TimeoutException:
        available = [
            el.text.strip()
            for el in driver.find_elements(
                By.CSS_SELECTOR,
                ".dropdown-menu.open .dropdown-menu.inner li a span.text",
            )
        ]
        logger.warning(
            "filters_option_not_found",
            label=label,
            wanted=option_text,
            available=available,
        )
        # Close the dangling open dropdown.
        try:
            trigger.click()
        except Exception:
            pass


def _select_all_options(
    driver: WebDriver,
    wait: WebDriverWait,
    timeout: int,
    trigger_locator: tuple,
    label: str,
) -> None:
    """
    Open a Bootstrap Select dropdown and click its "Select All" button.
    Falls back to clicking each unselected option individually if no button exists.
    """
    trigger = _wait_for_enabled(driver, timeout, trigger_locator, label)
    if trigger is None:
        return

    try:
        trigger.click()
    except Exception:
        driver.execute_script("arguments[0].click();", trigger)
    time.sleep(_DROPDOWN_PAUSE_S)

    # Prefer the explicit "Select All" button.
    btns = [b for b in driver.find_elements(*FilterForm.SELECT_ALL_BUTTON) if b.is_displayed()]
    if btns:
        btns[0].click()
        logger.info("filters_select_all_clicked", label=label)
    else:
        opts = driver.find_elements(
            By.CSS_SELECTOR,
            ".dropdown-menu.open .dropdown-menu.inner li:not(.selected) a",
        )
        clicked = sum(1 for o in opts if o.is_displayed() and (o.click() or True))
        logger.info("filters_options_individually_selected", label=label, count=clicked)

    # Close dropdown.
    try:
        trigger.click()
    except Exception:
        pass
    time.sleep(0.2)


def _fill_date_input(driver: WebDriver, element: WebElement, value: str) -> None:
    """
    Write a date string into a jQuery UI datepicker input via JavaScript,
    then fire a change event and Tab out to close any open calendar popup.
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
    Wait until DataTables has finished processing the search AJAX response.

    Strategy:
      1. Wait for pre_tbody to become stale (DataTables replaces <tbody> on
         every render, including 0-result searches) OR the no-results cell to
         appear — whichever fires first.
      2. Poll up to 10 s for the final outcome:
           - "Tabla sin información" cell visible  → 0 results
           - row count changed from snapshot       → data returned
    """
    logger.debug("filters_waiting_for_results", previous_row_count=previous_row_count)

    if pre_tbody is not None:
        try:
            def _stale_or_empty(d: WebDriver) -> bool:
                no_results = d.find_elements(*ResultTable.NO_RESULTS_MESSAGE)
                if no_results and no_results[0].is_displayed():
                    return True
                try:
                    pre_tbody.is_enabled()
                    return False
                except StaleElementReferenceException:
                    return True

            WebDriverWait(driver, timeout).until(
                _stale_or_empty,
                message="DataTables tbody did not become stale after Buscar",
            )
            logger.debug("filters_tbody_became_stale")
        except TimeoutException:
            logger.warning(
                "filters_tbody_staleness_timeout",
                hint="DataTables did not rebuild tbody within timeout",
            )

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        no_results = driver.find_elements(*ResultTable.NO_RESULTS_MESSAGE)
        if no_results and no_results[0].is_displayed():
            logger.info("filters_search_returned_no_results")
            return
        current = _count_table_rows(driver)
        if current != previous_row_count:
            logger.info("filters_results_loaded", new_count=current)
            return
        time.sleep(_POLL_INTERVAL_S)

    logger.warning(
        "filters_results_ambiguous",
        row_count=_count_table_rows(driver),
        hint="Neither empty-state nor row-count change detected — check ResultTable selectors",
    )
