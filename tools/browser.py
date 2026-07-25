"""
Browser tool — opens URLs, websites, and performs Google searches.

Implements BaseTool to provide web browsing capabilities using
Python's standard webbrowser module. Completely isolated from
the core framework — communicates only through the BaseTool interface.
"""

import logging
import webbrowser
from urllib.parse import quote_plus

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
                description="Opens a URL in the default browser.",
                required_args=["url"]
            ),
            "open_site": ActionDefinition(
                name="open_site",
                description=f"Opens a known website by name. Known sites: {site_list}",
                required_args=["site"]
            ),
            "search_google": ActionDefinition(
                name="search_google",
                description="Searches Google with a query.",
                required_args=["query"]
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
        dispatch: dict[str, callable] = {
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
            webbrowser.open(url)
            logger.info("Opened URL: %s", url)
            return f"Opened {url}"
        except webbrowser.Error as exc:
            raise ExecutionError(
                f"Failed to open URL '{url}': {exc}"
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
        site_name = args.get("site", "").lower().strip()

        if not site_name:
            raise ExecutionError("Missing required argument: 'site'")

        url = _KNOWN_SITES.get(site_name)

        if url is None:
            known = ", ".join(_KNOWN_SITES.keys())
            raise ExecutionError(
                f"Unknown site: '{site_name}'. "
                f"Known sites: {known}"
            )

        try:
            webbrowser.open(url)
            logger.info("Opened site: %s (%s)", site_name, url)
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
            webbrowser.open(url)
            logger.info("Google search: %s", query)
            return f"Searched Google for '{query}'"
        except webbrowser.Error as exc:
            raise ExecutionError(
                f"Failed to search Google: {exc}"
            ) from exc
