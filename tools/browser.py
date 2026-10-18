"""
Browser tool — opens URLs, known websites, and performs Google searches.

Implements BaseTool to provide web browsing capabilities using
Python's standard webbrowser module. Page-load and DOM verification belong to
the crash-safe mission runner; webbrowser.open alone cannot prove a page loaded.
"""

import ipaddress
import logging
import re
import webbrowser
from urllib.parse import quote_plus, urlsplit, urlunsplit

from core.action_definition import ActionDefinition
from core.exceptions import ExecutionError
from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

_MAX_URL_CHARS = 4096
_MAX_SEARCH_CHARS = 2000
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

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


def normalize_http_url(raw_url: object) -> str:
    """Normalize a URL to HTTP(S), rejecting ambiguous or unsafe destinations.

    Bare hostnames/domains are accepted and receive an HTTPS scheme. Explicit
    non-HTTP(S) schemes, credentials, malformed ports, control characters,
    whitespace/backslashes in the authority, and invalid host labels fail closed.
    """
    if not isinstance(raw_url, str):
        raise ExecutionError("URL must be a string.")
    url = raw_url.strip()
    if not url:
        raise ExecutionError("URL cannot be empty.")
    if len(url) > _MAX_URL_CHARS:
        raise ExecutionError(f"URL exceeds the {_MAX_URL_CHARS}-character limit.")
    if _CONTROL_CHARS.search(url):
        raise ExecutionError("URL contains control characters.")

    # Distinguish an explicit scheme from a bare domain before adding HTTPS.
    explicit_scheme = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*):", url)
    if explicit_scheme:
        if explicit_scheme.group(1).casefold() not in {"http", "https"}:
            raise ExecutionError("Only HTTP and HTTPS URLs are supported.")
    else:
        url = "https://" + url

    try:
        parsed = urlsplit(url)
        port = parsed.port  # Force malformed/out-of-range port validation.
    except ValueError as exc:
        raise ExecutionError("URL is malformed; verify its host and port.") from exc

    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise ExecutionError("URL must contain a valid HTTP(S) destination host.")
    if parsed.username is not None or parsed.password is not None:
        raise ExecutionError("URLs containing username/password credentials are not permitted.")
    if any(char.isspace() for char in parsed.netloc) or "\\" in parsed.netloc:
        raise ExecutionError("URL authority contains invalid whitespace or backslashes.")
    if port is not None and not 1 <= port <= 65535:
        raise ExecutionError("URL port must be between 1 and 65535.")

    hostname = parsed.hostname
    try:
        if ":" in hostname:
            ipaddress.IPv6Address(hostname)
        else:
            ascii_host = hostname.encode("idna").decode("ascii")
            if len(ascii_host) > 253:
                raise ValueError("host is too long")
            host_core = ascii_host.rstrip(".")
            labels = host_core.split(".")
            if not host_core or any(
                not label
                or len(label) > 63
                or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                for label in labels
            ):
                raise ValueError("invalid host label")
            if re.fullmatch(r"[0-9.]+", host_core):
                ipaddress.IPv4Address(host_core)
    except (UnicodeError, ValueError) as exc:
        raise ExecutionError("URL host is invalid.") from exc

    return urlunsplit((parsed.scheme.casefold(), parsed.netloc, parsed.path, parsed.query, parsed.fragment))



def build_browser_target(action: str, args: dict) -> str:
    """Validate and normalize the destination for one registered browser action."""
    if not isinstance(args, dict):
        raise ExecutionError("Browser arguments must be a JSON object.")

    if action == "open_url":
        return normalize_http_url(args.get("url"))

    if action == "open_site":
        raw_site = args.get("site")
        if not isinstance(raw_site, str):
            raise ExecutionError("Argument 'site' must be a string.")
        if not raw_site.strip():
            raise ExecutionError("Missing required argument: 'site'")
        site_name = raw_site.strip().casefold()
        clean_site = re.sub(r"^(?:open|go\s+to|visit|browse\s+to)\s+", "", site_name).strip()
        clean_site = re.sub(r"^(https?://)?(www\.)?", "", clean_site).strip().rstrip("/")
        clean_site = clean_site.split("/", 1)[0]
        target = _KNOWN_SITES.get(clean_site)
        if target is None and "." in clean_site and not clean_site.endswith("."):
            # Preserve friendly-domain normalization (e.g. github.com -> github's canonical URL).
            target = _KNOWN_SITES.get(clean_site.split(".", 1)[0])
            if target is None:
                target = normalize_http_url(clean_site)
        if target is None:
            known = ", ".join(_KNOWN_SITES.keys())
            raise ExecutionError(f"Unknown site: '{raw_site}'. Known sites: {known}")
        return normalize_http_url(target)

    if action == "search_google":
        query = args.get("query")
        if not isinstance(query, str):
            raise ExecutionError("Argument 'query' must be a string.")
        query = query.strip()
        if not query:
            raise ExecutionError("Missing required argument: 'query'")
        if len(query) > _MAX_SEARCH_CHARS:
            raise ExecutionError(f"Search query exceeds the {_MAX_SEARCH_CHARS}-character limit.")
        if _CONTROL_CHARS.search(query):
            raise ExecutionError("Search query contains control characters.")
        return normalize_http_url(_GOOGLE_SEARCH_URL.format(query=quote_plus(query)))

    raise ExecutionError(f"Unknown browser action: '{action}'")


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
        return "browser"

    @property
    def description(self) -> str:
        return "Open HTTP(S) websites and request Google searches in the default browser"

    def get_actions(self) -> dict[str, ActionDefinition]:
        site_list = ", ".join(_KNOWN_SITES.keys())
        return {
            "open_url": ActionDefinition(
                name="open_url",
                description=(
                    "Requests that an HTTP(S) URL open in the default browser. "
                    "The direct BrowserTool does not verify page load/content; the crash-safe "
                    "mission runner can perform independent postcondition checks."
                ),
                required_args=["url"],
                optional_args=["expected_text", "expected_title", "capture_page_excerpt"],
            ),
            "open_site": ActionDefinition(
                name="open_site",
                description=(
                    f"Opens a known website or an HTTP(S) domain in the default browser. Known sites: {site_list}. "
                    "Direct BrowserTool does not verify page load/content; postconditions require the crash-safe runner."
                ),
                required_args=["site"],
                optional_args=["expected_text", "expected_title", "capture_page_excerpt"],
            ),
            "search_google": ActionDefinition(
                name="search_google",
                description=(
                    "Requests a Google search in the default browser. The direct BrowserTool does not verify "
                    "page load/content; postconditions require the crash-safe mission runner."
                ),
                required_args=["query"],
                optional_args=["expected_text", "expected_title", "capture_page_excerpt"],
            ),
        }

    def execute(self, action: str, args: dict) -> str:
        args = self.validate_action_call(action, args)
        dispatch = {
            "open_url": self._open_url,
            "open_site": self._open_site,
            "search_google": self._search_google,
        }
        handler = dispatch.get(action)
        if handler is None:
            raise ExecutionError(f"Unknown browser action: '{action}'")
        return handler(args)

    @staticmethod
    def _open_url(args: dict) -> str:
        url = build_browser_target("open_url", args)
        if not webbrowser.open(url):
            raise ExecutionError("The default browser did not accept the URL open request.")
        logger.info("Browser open request accepted: %s", _safe_url_for_log(url))
        return (
            f"Browser open request accepted for {_safe_url_for_log(url)}. "
            "Page load and page content were not verified by BrowserTool."
        )

    @staticmethod
    def _open_site(args: dict) -> str:
        raw_site = args.get("site")
        if not isinstance(raw_site, str):
            raise ExecutionError("Argument 'site' must be a string.")
        url = build_browser_target("open_site", args)
        if not webbrowser.open(url):
            raise ExecutionError("The default browser did not accept the site open request.")
        logger.info("Browser open request accepted for site: %s", _safe_url_for_log(url))
        return (
            f"Opened a request to visit '{raw_site.strip()}' in the default browser. "
            "The open request was accepted; page load/content was not verified by BrowserTool."
        )

    @staticmethod
    def _search_google(args: dict) -> str:
        query = args.get("query")
        if not isinstance(query, str):
            raise ExecutionError("Argument 'query' must be a string.")
        query = query.strip()
        url = build_browser_target("search_google", args)
        if not webbrowser.open(url):
            raise ExecutionError("The default browser did not accept the search request.")
        logger.info("Google search open request accepted (query_chars=%d)", len(query))
        return (
            f"Google search open request accepted for '{query}'. "
            "Page load and search results were not verified by BrowserTool."
        )
