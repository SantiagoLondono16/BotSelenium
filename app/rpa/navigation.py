"""
Portal navigation — Facturación → Generar Factura.

Assumes the user is already authenticated (perform_login has been called).
All selectors are imported from selectors.py — do not add locators here.
"""

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.remote.webelement import WebElement

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.rpa.selectors import MainNav

logger = get_logger(__name__)


class NavigationError(Exception):
    """Raised when the bot cannot reach the target page."""


def go_to_generar_factura(driver: WebDriver, settings: Settings | None = None) -> None:
    """
    Click through the main menu to land on the Generar Factura page.

    Flow:
      1. Click the "Facturación" top-level menu item.
      2. Wait for the submenu to appear.
      3. Click "Generar Factura".
      4. Wait for the page-ready indicator.

    Raises:
        NavigationError: on timeout at any step.
    """
    if settings is None:
        settings = get_settings()

    timeout = settings.selenium_timeout_seconds
    wait = WebDriverWait(driver, timeout)

    logger.info("navigation_start", target="Facturación > Generar Factura")

    try:
        # ── Step 1: open Facturación menu ─────────────────────────────────────
        facturacion = _find_clickable(driver, wait, MainNav.FACTURACION_MENU, MainNav.FACTURACION_MENU_FALLBACK, timeout, "Facturación menu")
        _safe_click(driver, facturacion)
        logger.debug("navigation_facturacion_clicked")

        # ── Step 2: click Generar Factura ─────────────────────────────────────
        generar = _find_clickable(driver, wait, MainNav.GENERAR_FACTURA_ITEM, MainNav.GENERAR_FACTURA_ITEM_FALLBACK, timeout, "Generar Factura item")
        _safe_click(driver, generar)
        logger.debug("navigation_generar_factura_clicked")

        # ── Step 3: confirm page is ready ─────────────────────────────────────
        wait.until(
            EC.visibility_of_element_located(MainNav.GENERAR_FACTURA_PAGE_READY),
            message=f"Generar Factura page-ready indicator not visible after {timeout}s",
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
            "Verify the selector placeholders in selectors.py → MainNav."
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
