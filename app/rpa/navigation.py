"""
Portal navigation — Facturación → Generar Factura.

Assumes the user is already authenticated (perform_login has been called).
All selectors are imported from selectors.py — do not add locators here.
"""

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from selenium.webdriver.remote.webelement import WebElement

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.rpa.selectors import HeadquarterSelect, MainNav

logger = get_logger(__name__)


class NavigationError(Exception):
    """Raised when the bot cannot reach the target page."""


def go_to_generar_factura(driver: WebDriver, settings: Settings | None = None) -> None:
    """
    Select the working sede then click through the main menu to reach
    the Generar Factura page.

    Flow:
      1. Select the configured sede from the Cambio de sede dropdown.
      2. Wait 1 s for the sede modal to close and portal to register the change.
      3. Click the "Facturación" top-level menu item.
      4. Click "Generar Factura" in the submenu.
      5. Wait for the URL to contain "consulta_ordenes_facturar".

    Raises:
        NavigationError: on timeout at any step.
    """
    if settings is None:
        settings = get_settings()

    timeout = settings.selenium_timeout_seconds
    wait = WebDriverWait(driver, timeout)

    logger.info("navigation_start", target="Facturación > Generar Factura")

    try:
        # ── Step 0: select working sede ───────────────────────────────────────
        _select_sede(driver, wait)
        # Brief pause to allow the sede modal to close and the portal to
        # register the sede change before menu interactions are attempted.
        import time as _time
        _time.sleep(1)

        # ── Step 1: open Facturación menu ─────────────────────────────────────
        facturacion = _find_clickable(
            driver, wait, MainNav.FACTURACION_MENU,
            MainNav.FACTURACION_MENU_FALLBACK, timeout, "Facturación menu",
        )
        _safe_click(driver, facturacion)
        logger.debug("navigation_facturacion_clicked")

        # ── Step 2: click Generar Factura ─────────────────────────────────────
        generar = _find_clickable(
            driver, wait, MainNav.GENERAR_FACTURA_ITEM,
            MainNav.GENERAR_FACTURA_ITEM_FALLBACK, timeout, "Generar Factura item",
        )
        _safe_click(driver, generar)
        logger.debug("navigation_generar_factura_clicked")

        # ── Step 3: confirm URL changed to the billing page ───────────────────
        wait.until(
            EC.url_contains("consulta_ordenes_facturar"),
            message=f"URL did not change to consulta_ordenes_facturar after {timeout}s",
        )
        logger.info("navigation_complete", current_url=driver.current_url)

    except TimeoutException as exc:
        current_url = driver.current_url
        logger.error(
            "navigation_timeout",
            current_url=current_url,
            detail=str(exc),
        )
        raise NavigationError(
            f"Could not navigate to Generar Factura — stopped at {current_url}. "
            "Verify MainNav selectors in selectors.py."
        ) from exc


# ── Helpers ───────────────────────────────────────────────────────────────────


def _find_clickable(
    driver: WebDriver,
    wait: WebDriverWait,
    primary: tuple,
    fallback: tuple,
    timeout: int,
    label: str,
) -> WebElement:
    """
    Try to find a clickable element using the primary locator.
    If the primary times out, retry once with the fallback locator.
    Logs which strategy succeeded so selectors.py can be narrowed down later.
    """
    try:
        el = wait.until(
            EC.element_to_be_clickable(primary),
            message=f"{label} not clickable with primary selector after {timeout}s",
        )
        logger.debug("nav_found_primary", label=label, locator=str(primary))
        return el
    except TimeoutException:
        logger.warning(
            "nav_primary_failed_trying_fallback",
            label=label,
            primary=str(primary),
            fallback=str(fallback),
        )
        # Short wait for fallback — the element should already be in the DOM
        short_wait = WebDriverWait(driver, min(timeout, 15))
        el = short_wait.until(
            EC.element_to_be_clickable(fallback),
            message=f"{label} not clickable with fallback selector either",
        )
        logger.debug("nav_found_fallback", label=label, locator=str(fallback))
        return el


def _safe_click(driver: WebDriver, element: WebElement) -> None:
    """
    Click an element.  If a normal click raises (e.g. obscured by overlay),
    fall back to a JavaScript click which bypasses visibility checks.
    """
    try:
        element.click()
    except Exception:
        logger.warning("nav_click_failed_js_fallback")
        driver.execute_script("arguments[0].click();", element)


def _select_sede(driver: WebDriver, wait: WebDriverWait) -> None:
    """
    Open the 'Cambio de sede' dialog and select the configured sede.

    This is required by Aquila immediately after login — the system defaults
    to no sede and billing queries return no results without this step.
    If the trigger element is not found (e.g. the user's account has a fixed
    sede), the step is skipped gracefully.
    """
    try:
        trigger = wait.until(
            EC.element_to_be_clickable(HeadquarterSelect.CAMBIO_SEDE_TRIGGER),
            message="Cambio de sede trigger not found",
        )
        _safe_click(driver, trigger)
        logger.debug("nav_sede_dialog_opened")

        dropdown_el = wait.until(
            EC.presence_of_element_located(HeadquarterSelect.DROPDOWN),
            message="change_headquarter dropdown not found",
        )
        # Wait for AJAX to populate options before reading them
        try:
            wait.until(
                EC.text_to_be_present_in_element(
                    HeadquarterSelect.DROPDOWN,
                    HeadquarterSelect.SEDE_NAME,
                )
            )
        except TimeoutException:
            pass  # Will fall back to first available option below

        sel = Select(dropdown_el)
        all_options = [o.text.strip() for o in sel.options if o.text.strip()]
        logger.debug("nav_sede_options_available", options=all_options)

        target = HeadquarterSelect.SEDE_NAME
        if target in all_options:
            sel.select_by_visible_text(target)
        elif all_options:
            target = all_options[0]
            sel.select_by_visible_text(target)
            logger.warning(
                "nav_sede_name_not_found_used_first",
                configured=HeadquarterSelect.SEDE_NAME,
                used=target,
            )
        else:
            raise NavigationError("Sede dropdown is empty after waiting")
        logger.info("nav_sede_selected", sede=target)

    except TimeoutException:
        logger.warning(
            "nav_sede_select_skipped",
            hint="'Cambio de sede' not present — sede may be pre-assigned for this account",
        )
