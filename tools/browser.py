"""
Browser tool — opens URLs, websites, and performs Google searches.

Implements BaseTool to provide web browsing capabilities using
Python's standard webbrowser module. Completely isolated from
the core framework — communicates only through the BaseTool interface.
"""

import logging
import re
import webbrowser
from urllib.parse import quote_plus, urlsplit

from core.action_definition import ActionDefinition
from core.exceptions import ExecutionError
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

# Map of friendly site names to their URLs
_KNOWN_SITES: dict[str, str] = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "stackoverflow": "https://stackoverflow.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://twitter.com",
    "x": "https://twitter.com",
    "linkedin": "https://www.linkedin.com",
    "wikipedia": "https://www.wikipedia.org",
    "chatgpt": "https://chat.openai.com",
    "amazon": "https://www.amazon.com",
    "netflix": "https://www.netflix.com",
    "whatsapp": "https://web.whatsapp.com",
}

_GOOGLE_SEARCH_URL = "https://www.google.com/search?q={query}"


def _safe_url_for_log(url: str) -> str:
    """Return URL location evidence without userinfo, query values, or fragments."""
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError:
        return "[invalid URL]"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    authority = host + (f":{port}" if port is not None else "")
    suffix = "?[redacted]" if parsed.query else ""
    suffix += "#[redacted]" if parsed.fragment else ""
    return f"{parsed.scheme}://{authority}{parsed.path}{suffix}"


class BrowserTool(BaseTool):
    """Tool for opening URLs, known websites, and Google searches."""

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return "browser"

    @property
    def description(self) -> str:
        """Human-readable description for LLM prompts."""
        return "Open websites, URLs, and perform Google searches"

    def get_actions(self) -> dict[str, ActionDefinition]:
        """Return available actions and their structured definitions.

        Returns:
            Dict mapping action names to ActionDefinition objects.
        """
        from core.action_definition import ActionDefinition
        
        site_list = ", ".join(_KNOWN_SITES.keys())

        return {
            "open_url": ActionDefinition(
                name="open_url",
                description="Opens a URL in the default browser and can verify expected page text/title when local Chromium inspection is enabled.",
                required_args=["url"],
                optional_args=["expected_text", "expected_title", "capture_page_excerpt"],
            ),
            "open_site": ActionDefinition(
                name="open_site",
                description=f"Opens a known website by name and can verify expected page text/title when local Chromium inspection is enabled. Known sites: {site_list}",
                required_args=["site"],
                optional_args=["expected_text", "expected_title", "capture_page_excerpt"],
            ),
            "search_google": ActionDefinition(
                name="search_google",
                description="Searches Google with a query and can verify expected result text/title when local Chromium inspection is enabled.",
                required_args=["query"],
                optional_args=["expected_text", "expected_title", "capture_page_excerpt"],
            ),
        }

    def execute(self, action: str, args: dict) -> str:
        """Execute a browser action.

        Args:
            action: The action to perform.
            args: Arguments for the action.

        Returns:
            Human-readable result string.

        Raises:
            ExecutionError: If the action fails or args are missing.
        """
        from collections.abc import Callable
        dispatch: dict[str, Callable] = {
            "open_url": self._open_url,
            "open_site": self._open_site,
            "search_google": self._search_google,
        }

        handler = dispatch.get(action)

        if handler is None:
            raise ExecutionError(
                f"Unknown browser action: '{action}'"
            )

        return handler(args)

    @staticmethod
    def _open_url(args: dict) -> str:
        """Open a URL in the default browser.

        Args:
            args: Must contain 'url' key.

        Returns:
            Success message.

        Raises:
            ExecutionError: If 'url' is missing or open fails.
        """
        url = args.get("url", "").strip()

        if not url:
            raise ExecutionError("Missing required argument: 'url'")

        # Add https:// if no scheme is provided
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            if not webbrowser.open(url):
                raise ExecutionError("The default browser did not accept the URL open request.")
            logger.info("Opened URL: %s", _safe_url_for_log(url))
            return f"Opened {_safe_url_for_log(url)}"
        except webbrowser.Error as exc:
            raise ExecutionError(
                f"Failed to open URL '{_safe_url_for_log(url)}': {exc}"
            ) from exc

    @staticmethod
    def _open_site(args: dict) -> str:
        """Open a known website by friendly name.

        Args:
            args: Must contain 'site' key.

        Returns:
            Success message.

        Raises:
            ExecutionError: If site is unknown or open fails.
        """
        raw_site = args.get("site", "").strip()
        if not raw_site:
            raise ExecutionError("Missing required argument: 'site'")

        # Clean prefix and lowercase
        site_name = raw_site.lower().strip()
        clean_site = re.sub(r"^(?:open|go\s+to|visit|browse\s+to)\s+", "", site_name).strip()
        clean_site = re.sub(r"^(https?:\/\/)?(www\.)?", "", clean_site).strip().rstrip("/")
        # Extract base domain name if path exists
        clean_site = clean_site.split("/")[0]

        # 1. Exact match in known sites
        url = _KNOWN_SITES.get(clean_site)

        # 2. Match without domain extension (e.g. 'github.com' -> 'github')
        if url is None and "." in clean_site:
            base_name = clean_site.split(".")[0]
            url = _KNOWN_SITES.get(base_name)

        # 3. Direct domain fallback if valid domain format (e.g. huggingface.co)
        if url is None and "." in clean_site and not clean_site.endswith("."):
            url = f"https://{clean_site}"

        if url is None:
            known = ", ".join(_KNOWN_SITES.keys())
            raise ExecutionError(
                f"Unknown site: '{raw_site}'. "
                f"Known sites: {known}"
            )

        try:
            if not webbrowser.open(url):
                raise ExecutionError("The default browser did not accept the site open request.")
            logger.info("Opened site: %s (%s)", site_name, _safe_url_for_log(url))
            return f"Opened {site_name}"
        except webbrowser.Error as exc:
            raise ExecutionError(
                f"Failed to open {site_name}: {exc}"
            ) from exc

    @staticmethod
    def _search_google(args: dict) -> str:
        """Search Google with a query string.

        Args:
            args: Must contain 'query' key.

        Returns:
            Success message.

        Raises:
            ExecutionError: If query is missing or search fails.
        """
        query = args.get("query", "").strip()

        if not query:
            raise ExecutionError(
                "Missing required argument: 'query'"
            )

        url = _GOOGLE_SEARCH_URL.format(query=quote_plus(query))

        try:
            if not webbrowser.open(url):
                raise ExecutionError("The default browser did not accept the search request.")
            logger.info("Google search requested (query_chars=%d)", len(query))
            return f"Searched Google for '{query}'"
        except webbrowser.Error as exc:
            raise ExecutionError(
                f"Failed to search Google: {exc}"
            ) from exc
