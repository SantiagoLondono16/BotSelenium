"""
Portal login flow.

Steps:
  1. driver.get(PORTAL_URL)
  2. Wait for username field → fill credentials
  3. Wait for submit button → click
  4. Detect success (POST_LOGIN_INDICATOR) or failure (LOGIN_ERROR_MESSAGE / timeout)

All selectors are imported from selectors.py — do not add locators here.
"""

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.rpa.selectors import LoginPage

logger = get_logger(__name__)


class LoginError(Exception):
    """Raised when the portal login cannot be completed."""


def perform_login(driver: WebDriver, settings: Settings | None = None) -> None:
    """
    Navigate to the portal URL and authenticate.

    Uses only explicit waits (WebDriverWait + expected_conditions).
    Raises LoginError on timeout or when the portal shows an explicit error message.

    Args:
        driver:   Active Remote WebDriver session.
        settings: App settings; if None, loaded from environment.
    """
    if settings is None:
        settings = get_settings()

    timeout = settings.selenium_timeout_seconds
    wait = WebDriverWait(driver, timeout)

    logger.info("login_start", portal_url=settings.portal_url)

    # ── Step 1: navigate ──────────────────────────────────────────────────────
    driver.get(settings.portal_url)
    login_page_url = driver.current_url
    logger.debug("login_page_loaded", current_url=login_page_url)

    try:
        # ── Step 2: fill username ─────────────────────────────────────────────
        logger.debug("login_waiting_for_username_field", locator=str(LoginPage.USERNAME))
        username_el = wait.until(
            EC.visibility_of_element_located(LoginPage.USERNAME),
            message=f"Username field not visible after {timeout}s",
        )
        username_el.clear()
        username_el.send_keys(settings.portal_username)
        logger.debug("login_username_entered")

        # ── Step 3: fill password ─────────────────────────────────────────────
        logger.debug("login_waiting_for_password_field", locator=str(LoginPage.PASSWORD))
        password_el = wait.until(
            EC.visibility_of_element_located(LoginPage.PASSWORD),
            message=f"Password field not visible after {timeout}s",
        )
        password_el.clear()
        password_el.send_keys(settings.portal_password)
        logger.debug("login_password_entered")

        # ── Step 4: submit ────────────────────────────────────────────────────
        logger.debug("login_waiting_for_submit_button", locator=str(LoginPage.SUBMIT_BUTTON))
        submit_btn = wait.until(
            EC.element_to_be_clickable(LoginPage.SUBMIT_BUTTON),
            message=f"Submit button not clickable after {timeout}s",
        )
        submit_btn.click()
        logger.debug("login_submitted")

        # ── Step 5: confirm success OR detect explicit error ──────────────────
        # Accept any of:
        #   (a) a DOM element that only appears on the authenticated dashboard
        #   (b) the portal's own error banner (wrong credentials)
        #   (c) a URL change away from the login page — many portals simply
        #       redirect to the home/dashboard without rendering a specific
        #       landmark element, so URL-change is the most portable signal.
        _wait_for_login_outcome(driver, wait, login_page_url)

    except TimeoutException as exc:
        _log_and_raise_login_error(driver, exc)


def _wait_for_login_outcome(
    driver: WebDriver,
    wait: WebDriverWait,
    login_page_url: str,
) -> None:
    """
    Wait until the portal signals login success or an explicit error.

    Uses EC.any_of so that WebDriverWait drives all polling internally —
    no time.sleep() required.  The first condition to become true unblocks.

    Success signals (any of):
      - POST_LOGIN_INDICATOR element appears (preferred, most specific)
      - URL changes away from the login page (fallback for redirect-only portals)

    Failure signals:
      - LOGIN_ERROR_MESSAGE element appears

    Raises LoginError immediately if an error banner is detected.
    Raises LoginError (wrapping TimeoutException) if no condition fires in time.
    """
    wait.until(
        EC.any_of(
            EC.visibility_of_element_located(LoginPage.POST_LOGIN_INDICATOR),
            EC.visibility_of_element_located(LoginPage.LOGIN_ERROR_MESSAGE),
            EC.url_changes(login_page_url),   # redirect-based portals
        ),
        message="Login did not complete within timeout (no indicator, no error, no redirect)",
    )

    # If the portal showed an explicit error banner, surface it immediately.
    error_els = driver.find_elements(*LoginPage.LOGIN_ERROR_MESSAGE)
    if error_els and error_els[0].is_displayed():
        msg = error_els[0].text.strip() or "Portal showed a login error message"
        logger.error("login_error_banner", message=msg)
        raise LoginError(f"Login rejected by portal: {msg}")

    logger.info("login_success", current_url=driver.current_url)


def _log_and_raise_login_error(driver: WebDriver, exc: TimeoutException) -> None:
    current_url = driver.current_url
    logger.error(
        "login_timeout",
        current_url=current_url,
        detail=str(exc),
    )
    raise LoginError(
        f"Login timed out — stopped at {current_url}. "
        "Check PORTAL_URL, PORTAL_USERNAME, PORTAL_PASSWORD env vars "
        "and verify the selector placeholders in selectors.py."
    ) from exc
