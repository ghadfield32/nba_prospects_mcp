"""Browser-based web scraping for JavaScript-rendered pages

Provides Playwright-based scraping for websites that require JavaScript execution.
Falls back gracefully if Playwright is not installed.

Key Features:
- Optional Playwright dependency (code works without it)
- Browser instance reuse for efficiency
- Automatic cleanup and error handling
- Configurable timeouts and wait strategies
- UTF-8 support for international characters

Usage:
    from cbb_data.fetchers.browser_scraper import BrowserScraper

    # Basic usage
    scraper = BrowserScraper()
    html = scraper.get_rendered_html("https://example.com")
    scraper.close()

    # Context manager (recommended)
    with BrowserScraper() as scraper:
        html = scraper.get_rendered_html("https://example.com")
        tables = scraper.get_tables("https://example.com")

Installation:
    Optional dependency - install with:
    uv pip install playwright
    playwright install chromium
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class BrowserScraper:
    """Browser-based web scraper using Playwright (optional dependency)

    Handles JavaScript-rendered pages by using a real browser. Falls back
    gracefully if Playwright is not installed.

    Attributes:
        browser: Playwright browser instance (lazy-initialized)
        context: Browser context for isolation
        page: Browser page for navigation
        headless: Whether to run browser in headless mode
        timeout: Default timeout in milliseconds
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        slow_mo: int = 0,
        capture_network: bool = False,
    ):
        """Initialize browser scraper

        Args:
            headless: Run browser without UI (default: True)
            timeout: Page load timeout in milliseconds (default: 30000)
            slow_mo: Slow down operations by N milliseconds (for debugging)
            capture_network: Enable network request capturing (default: False)
        """
        self.headless = headless
        self.timeout = timeout
        self.slow_mo = slow_mo
        self.capture_network = capture_network

        # Lazy initialization - only create when needed
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

        # Network request storage
        self.captured_requests: list[dict] = []
        self.captured_responses: list[dict] = []

        # Check if Playwright is available
        self._playwright_available = self._check_playwright()

    def _check_playwright(self) -> bool:
        """Check if Playwright is installed

        Uses importlib.util.find_spec to test availability without importing.

        Returns:
            True if Playwright is available, False otherwise
        """
        import importlib.util

        spec = importlib.util.find_spec("playwright")
        if spec is None:
            logger.warning(
                "Playwright not installed. JavaScript-rendered pages unavailable. "
                "Install with: uv pip install playwright && playwright install chromium"
            )
            return False
        return True

    def _ensure_browser(self) -> None:
        """Ensure browser is initialized (lazy initialization)"""
        if self._browser is not None:
            return

        if not self._playwright_available:
            raise RuntimeError(
                "Playwright not installed. Cannot scrape JavaScript-rendered pages. "
                "Install with: uv pip install playwright && playwright install chromium"
            )

        try:
            from playwright.sync_api import sync_playwright

            logger.info("Initializing Playwright browser...")
            self._playwright = sync_playwright().start()  # type: ignore[assignment]
            self._browser = self._playwright.chromium.launch(  # type: ignore[attr-defined]
                headless=self.headless, slow_mo=self.slow_mo
            )
            self._context = self._browser.new_context(  # type: ignore[attr-defined]
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                locale="fr-FR",  # French locale for LNB
                timezone_id="Europe/Paris",
            )
            self._page = self._context.new_page()  # type: ignore[attr-defined]
            self._page.set_default_timeout(self.timeout)  # type: ignore[attr-defined]

            # Set up network request interception if enabled
            if self.capture_network:
                self._setup_network_capture()

            logger.info("Playwright browser initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Playwright browser: {e}")
            raise

    def _setup_network_capture(self) -> None:
        """Set up network request/response capturing"""
        if not self._page:
            return

        def handle_request(request: Any) -> None:
            """Capture outgoing requests"""
            self.captured_requests.append(
                {
                    "url": request.url,
                    "method": request.method,
                    "headers": request.headers,
                    "timestamp": time.time(),
                }
            )

        def handle_response(response: Any) -> None:
            """Capture incoming responses"""
            self.captured_responses.append(
                {
                    "url": response.url,
                    "status": response.status,
                    "headers": response.headers,
                    "timestamp": time.time(),
                }
            )

        self._page.on("request", handle_request)
        self._page.on("response", handle_response)

        logger.debug("Network request capturing enabled")

    def get_rendered_html(
        self, url: str, wait_for: str | None = None, wait_time: float = 2.0
    ) -> str:
        """Get fully-rendered HTML from a JavaScript page

        Args:
            url: URL to fetch
            wait_for: CSS selector to wait for (optional)
            wait_time: Additional time to wait after page load in seconds

        Returns:
            Fully-rendered HTML as string

        Raises:
            RuntimeError: If Playwright is not installed
            TimeoutError: If page load exceeds timeout
        """
        self._ensure_browser()

        logger.info(f"Fetching JavaScript-rendered page: {url}")

        try:
            # Navigate to page
            self._page.goto(url, wait_until="networkidle")  # type: ignore[attr-defined]

            # Wait for specific element if requested
            if wait_for:
                logger.debug(f"Waiting for element: {wait_for}")
                self._page.wait_for_selector(wait_for, state="visible")  # type: ignore[attr-defined]

            # Additional wait for dynamic content
            if wait_time > 0:
                logger.debug(f"Waiting {wait_time}s for dynamic content...")
                time.sleep(wait_time)

            # Get rendered HTML
            html: str = self._page.content()  # type: ignore[attr-defined]
            logger.info(f"Successfully fetched {len(html)} characters of HTML")

            return html

        except Exception as e:
            logger.error(f"Failed to fetch rendered HTML from {url}: {e}")
            raise

    def get_rendered_html_with_responses(
        self,
        url: str,
        wait_for: str | None = None,
        wait_time: float = 2.0,
        response_filter_keywords: tuple[str, ...] = ("shots", "shotchart", ".json"),
        debug_dir: Any = None,
    ) -> tuple[str, list[dict]]:
        """Get fully-rendered HTML and capture network responses for debugging

        This is a debug-only method that captures both the page HTML and all network
        responses matching filter keywords. Useful for debugging FIBA LiveStats where
        shot data may come from XHR/JSON responses rather than embedded in HTML.

        Args:
            url: URL to fetch
            wait_for: CSS selector to wait for (optional)
            wait_time: Additional time to wait after page load in seconds
            response_filter_keywords: Only capture responses whose URL contains these keywords
            debug_dir: If provided (Path object), write captured responses to this directory

        Returns:
            Tuple of (html_content, captured_responses)
            where captured_responses is a list of dicts with keys:
                - url: Response URL
                - status: HTTP status code
                - content_type: Content-Type header
                - text: Response body (if successfully retrieved)

        Raises:
            RuntimeError: If Playwright is not installed
            TimeoutError: If page load exceeds timeout

        Example:
            >>> from pathlib import Path
            >>> scraper = BrowserScraper()
            >>> debug_dir = Path("data/raw/fiba/debug/LKL/2023-24/301234_responses")
            >>> html, responses = scraper.get_rendered_html_with_responses(
            ...     "https://fibalivestats.dcd.shared.geniussports.com/u/LKL/301234/shotchart.html",
            ...     debug_dir=debug_dir
            ... )
            >>> print(f"Captured {len(responses)} network responses")
        """
        from pathlib import Path

        self._ensure_browser()

        logger.info(f"Fetching JavaScript-rendered page with network capture: {url}")

        captured: list[dict] = []

        def handle_response(response: Any) -> None:
            """Capture relevant network responses"""
            try:
                resp_url = response.url
                # Filter by keywords
                if not any(keyword in resp_url for keyword in response_filter_keywords):
                    return

                status = response.status
                headers = response.headers
                content_type = headers.get("content-type", "")

                # Try to get response body (best effort)
                try:
                    text = response.text()
                except Exception:
                    text = None

                captured.append({
                    "url": resp_url,
                    "status": status,
                    "content_type": content_type,
                    "text": text,
                })

                logger.debug(
                    "Captured response: %s (status=%d, content-type=%s, size=%d)",
                    resp_url,
                    status,
                    content_type,
                    len(text) if text else 0,
                )

            except Exception as exc:
                logger.debug("Failed to capture response: %s", exc)

        try:
            # Set up response listener
            self._page.on("response", handle_response)  # type: ignore[attr-defined]

            # Navigate to page
            self._page.goto(url, wait_until="networkidle")  # type: ignore[attr-defined]

            # Wait for specific element if requested
            if wait_for:
                logger.debug(f"Waiting for element: {wait_for}")
                self._page.wait_for_selector(wait_for, state="visible")  # type: ignore[attr-defined]

            # Additional wait for dynamic content
            if wait_time > 0:
                logger.debug(f"Waiting {wait_time}s for dynamic content...")
                time.sleep(wait_time)

            # Get rendered HTML
            html: str = self._page.content()  # type: ignore[attr-defined]

            logger.info(
                "Successfully fetched %d characters of HTML and captured %d network responses",
                len(html),
                len(captured),
            )

            # Optionally save to disk for debugging
            if debug_dir is not None:
                debug_path = Path(debug_dir)
                debug_path.mkdir(parents=True, exist_ok=True)

                # Save page HTML
                (debug_path / "page.html").write_text(html, encoding="utf-8")

                # Save each response
                for i, resp in enumerate(captured):
                    # Determine file extension
                    if resp["content_type"] and "json" in resp["content_type"]:
                        ext = "json"
                    else:
                        ext = "txt"

                    # Extract filename from URL (last path component)
                    try:
                        filename_base = Path(resp["url"]).name or f"response_{i}"
                    except Exception:
                        filename_base = f"response_{i}"

                    filename = f"{i:02d}_{resp['status']}_{filename_base}.{ext}"
                    filepath = debug_path / filename

                    if resp["text"]:
                        filepath.write_text(resp["text"], encoding="utf-8")

                logger.warning(
                    "Saved debug artifacts: page.html + %d responses to %s",
                    len(captured),
                    debug_path,
                )

            return html, captured

        except Exception as e:
            logger.error(f"Failed to fetch rendered HTML with responses from {url}: {e}")
            raise
        finally:
            # Clean up listener
            try:
                self._page.remove_listener("response", handle_response)  # type: ignore[attr-defined]
            except Exception:
                pass

    def get_tables(
        self, url: str, wait_for: str | None = "table", wait_time: float = 2.0
    ) -> list[str]:
        """Get all table HTML from a JavaScript page

        Args:
            url: URL to fetch
            wait_for: CSS selector to wait for (default: "table")
            wait_time: Additional time to wait in seconds

        Returns:
            List of table HTML strings
        """
        self._ensure_browser()

        logger.info(f"Fetching tables from: {url}")

        try:
            # Navigate and wait for tables
            self._page.goto(url, wait_until="networkidle")  # type: ignore[attr-defined]

            if wait_for:
                self._page.wait_for_selector(wait_for, state="visible")  # type: ignore[attr-defined]

            if wait_time > 0:
                time.sleep(wait_time)

            # Extract all tables
            tables = self._page.query_selector_all("table")  # type: ignore[attr-defined]
            table_htmls = [table.inner_html() for table in tables]

            logger.info(f"Found {len(table_htmls)} tables")
            return table_htmls

        except Exception as e:
            logger.error(f"Failed to fetch tables from {url}: {e}")
            raise

    def click_and_wait(
        self, selector: str, wait_for: str | None = None, wait_time: float = 1.0
    ) -> None:
        """Click an element and wait for page to update

        Args:
            selector: CSS selector of element to click
            wait_for: CSS selector to wait for after click
            wait_time: Additional time to wait in seconds
        """
        self._ensure_browser()

        logger.debug(f"Clicking element: {selector}")

        try:
            self._page.click(selector)  # type: ignore[attr-defined]

            if wait_for:
                self._page.wait_for_selector(wait_for, state="visible")  # type: ignore[attr-defined]

            if wait_time > 0:
                time.sleep(wait_time)

        except Exception as e:
            logger.error(f"Failed to click element {selector}: {e}")
            raise

    def clear_captured_requests(self) -> None:
        """Clear stored network requests and responses"""
        self.captured_requests = []
        self.captured_responses = []
        logger.debug("Cleared captured network requests")

    def get_requests_by_domain(self, domain: str) -> list[dict]:
        """Filter captured requests by domain

        Args:
            domain: Domain to filter by (e.g., "atriumsports.com")

        Returns:
            List of request dicts matching the domain
        """
        return [req for req in self.captured_requests if domain in req["url"]]

    def extract_uuid_from_requests(self, domain_pattern: str = "atriumsports.com") -> list[str]:
        """Extract UUIDs from captured requests

        Looks for UUID patterns (36-char hex with dashes) in request URLs.

        Args:
            domain_pattern: Filter requests by domain (default: "atriumsports.com")

        Returns:
            List of extracted UUIDs
        """
        import re

        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        uuids = []

        filtered_requests = self.get_requests_by_domain(domain_pattern)

        for req in filtered_requests:
            matches = re.findall(uuid_pattern, req["url"], re.IGNORECASE)
            uuids.extend(matches)

        # Return unique UUIDs
        return list(set(uuids))

    def get_current_url(self) -> str:
        """Get the current page URL

        Returns:
            Current page URL as string

        Raises:
            RuntimeError: If browser is not initialized
        """
        self._ensure_browser()

        if not self._page:
            raise RuntimeError("Browser page not initialized")

        return self._page.url

    def find_elements(self, selector: str) -> list:
        """Find all elements matching CSS selector

        Args:
            selector: CSS selector to match

        Returns:
            List of Playwright element handles

        Raises:
            RuntimeError: If browser is not initialized
        """
        self._ensure_browser()

        if not self._page:
            raise RuntimeError("Browser page not initialized")

        return self._page.query_selector_all(selector)

    def get_element_attribute(self, element: Any, attribute: str) -> str | None:
        """Get attribute value from an element

        Args:
            element: Playwright element handle
            attribute: Attribute name (e.g., "href", "data-id")

        Returns:
            Attribute value or None if not found
        """
        try:
            result: str | None = element.get_attribute(attribute)
            return result
        except Exception as e:
            logger.warning(f"Failed to get attribute {attribute}: {e}")
            return None

    def close(self) -> None:
        """Close browser and cleanup resources"""
        if self._browser:
            logger.info("Closing Playwright browser...")
            try:
                if self._page:
                    self._page.close()
                if self._context:
                    self._context.close()
                if self._browser:
                    self._browser.close()
                if self._playwright:
                    self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error during browser cleanup: {e}")
            finally:
                self._page = None
                self._context = None
                self._browser = None
                self._playwright = None
                logger.info("Browser closed")

    def __enter__(self) -> BrowserScraper:
        """Context manager entry"""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - ensures cleanup"""
        self.close()

    def __del__(self) -> None:
        """Destructor - ensures cleanup"""
        try:
            self.close()
        except Exception:
            pass


def is_playwright_available() -> bool:
    """Check if Playwright is available for use

    Uses importlib.util.find_spec to test availability without importing.

    Returns:
        True if Playwright is installed, False otherwise
    """
    import importlib.util

    return importlib.util.find_spec("playwright") is not None
