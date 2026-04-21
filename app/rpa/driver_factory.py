"""
WebDriver factory.

Responsibilities:
  - Build a Remote WebDriver pointed at the Selenium Grid container.
  - Apply all required Chrome options for running inside Docker.
  - Enforce zero implicit wait (all synchronization is done with explicit waits).
  - Provide a safe quit helper.
"""

import time

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# How many times to retry connecting to the Selenium container on startup.
# The container may still be initialising when the API first dispatches a job.
_CONNECT_RETRIES = 3
_CONNECT_RETRY_DELAY_S = 3


def create_driver(settings: Settings | None = None) -> WebDriver:
    """
    Connect to the Selenium standalone-chrome container and return a WebDriver.

    Retries up to _CONNECT_RETRIES times with a short sleep between attempts
    to tolerate the Selenium container being momentarily unready.

    Raises:
        WebDriverException: if the connection cannot be established after all retries.
    """
    if settings is None:
        settings = get_settings()

    options = _build_chrome_options(settings)

    last_exc: WebDriverException | None = None
    for attempt in range(1, _CONNECT_RETRIES + 1):
        try:
            logger.info(
                "driver_connecting",
                remote_url=settings.selenium_remote_url,
                attempt=attempt,
            )
            driver = webdriver.Remote(
                command_executor=settings.selenium_remote_url,
                options=options,
            )
            # Page-load timeout caps how long driver.get() will wait.
            driver.set_page_load_timeout(settings.selenium_timeout_seconds)
            # Implicit wait is intentionally 0 — we use WebDriverWait exclusively.
            driver.implicitly_wait(0)

            logger.info("driver_ready", session_id=driver.session_id)
            return driver

        except WebDriverException as exc:
            last_exc = exc
            logger.warning(
                "driver_connect_failed",
                attempt=attempt,
                max_attempts=_CONNECT_RETRIES,
                error=str(exc),
            )
            if attempt < _CONNECT_RETRIES:
                time.sleep(_CONNECT_RETRY_DELAY_S)

    raise WebDriverException(
        f"Could not connect to Selenium at {settings.selenium_remote_url} "
        f"after {_CONNECT_RETRIES} attempts."
    ) from last_exc


def quit_driver(driver: WebDriver) -> None:
    """
    Cleanly terminate the browser session.
    Errors during quit are logged but not re-raised — the job outcome has
    already been recorded by this point.
    """
    try:
        driver.quit()
        logger.info("driver_quit")
    except Exception as exc:
        logger.warning("driver_quit_error", error=str(exc))


def _build_chrome_options(settings: Settings) -> Options:
    options = Options()

    if settings.selenium_headless:
        # --headless=new is the modern flag (Chrome ≥ 112); avoids deprecated
        # --headless behaviour differences.
        options.add_argument("--headless=new")

    # Mandatory flags when Chrome runs inside a Docker container
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # Suppress the "Chrome is being controlled by automated software" banner.
    # This is cosmetic — it does not bypass any anti-bot detection.
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    return options
