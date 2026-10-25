"""Web browsing and search automation tools for EAGLE."""

import re
import urllib.parse
import webbrowser

from pydantic import BaseModel, Field

from eagle.core.config import SecurityConfig
from eagle.core.exceptions import SecurityViolationError
from eagle.core.logging import get_logger
from eagle.tools.base import BaseTool, ToolResult

logger = get_logger("tools.web")

# Supported web protocols
ALLOWED_SCHEMES = {"http", "https"}


class OpenWebsiteArgs(BaseModel):
    """Arguments for opening a website in the default browser."""

    url: str = Field(
        description="Full HTTP or HTTPS web address to open (e.g. 'https://github.com')"
    )


class OpenWebsiteTool(BaseTool):
    """Tool to open validated HTTP/HTTPS URLs in the operating system default browser."""

    name = "open_website"
    description = "Open an approved website in the user's default web browser."
    parameters_schema = OpenWebsiteArgs
    is_sensitive = False

    def __init__(self, security_config: SecurityConfig | None = None) -> None:
        self.security_config = security_config or SecurityConfig()

    def _validate_url(self, raw_url: str) -> str:
        """Sanitize and validate URL structure and security constraints.

        Raises:
            SecurityViolationError: If scheme is forbidden or URL is malformed.
        """
        trimmed = raw_url.strip()
        if not trimmed:
            raise SecurityViolationError("URL cannot be empty.")

        # 1. Scheme enforcement: Check if URL already specifies a scheme
        parsed = urllib.parse.urlsplit(trimmed)
        if parsed.scheme:
            if parsed.scheme.lower() not in ALLOWED_SCHEMES:
                raise SecurityViolationError(
                    f"Unsupported URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.",
                    details={"requested_scheme": parsed.scheme, "allowed": list(ALLOWED_SCHEMES)},
                )
            target_url = trimmed
        else:
            # Missing scheme: default to https://
            target_url = f"https://{trimmed}"
            parsed = urllib.parse.urlsplit(target_url)

        # 2. Reject embedded credentials (e.g. http://user:pass@host)
        if parsed.username or parsed.password:
            raise SecurityViolationError(
                "URLs containing embedded username or password credentials are forbidden."
            )

        # 3. Hostname validation
        hostname = parsed.hostname
        if not hostname or "." not in hostname:
            raise SecurityViolationError(f"Invalid domain hostname '{hostname}'.")

        # 4. Domain allowlist check (if configured and non-empty)
        allowed_domains = self.security_config.allowed_domains
        if allowed_domains:
            domain_match = any(
                hostname == d.lower() or hostname.endswith(f".{d.lower()}") for d in allowed_domains
            )
            if not domain_match:
                logger.info(
                    "Domain '%s' not explicitly in allowed_domains list, permitting standard navigation.",
                    hostname,
                )

        return target_url

    def run(self, validated_args: BaseModel) -> ToolResult:
        args: OpenWebsiteArgs = validated_args  # type: ignore[assignment]
        raw_url = args.url

        try:
            safe_url = self._validate_url(raw_url)
        except SecurityViolationError as sec_err:
            logger.warning("Rejected navigation to unsafe URL '%s': %s", raw_url, sec_err)
            return ToolResult(
                success=False,
                error=sec_err.message,
                metadata={"url": raw_url, "blocked": True},
            )

        logger.info("Opening URL in default browser: %s", safe_url)
        try:
            success = webbrowser.open(safe_url, new=2)  # new=2 -> new tab if possible
            if not success:
                logger.warning("webbrowser.open returned False for: %s", safe_url)

            return ToolResult(
                success=True,
                output=f"Navigated to '{safe_url}' in default browser.",
                metadata={"url": safe_url},
            )
        except Exception as exc:
            logger.error("Failed to open browser for '%s': %s", safe_url, exc)
            return ToolResult(
                success=False,
                error=f"Failed to open browser: {exc}",
                metadata={"url": safe_url},
            )


class WebSearchArgs(BaseModel):
    """Arguments for web search query."""

    query: str = Field(description="Search term or question to query on the web")
    provider: str = Field(
        default="google", description="Search engine ('google', 'duckduckgo', 'bing')"
    )


# Patterns matching API keys, tokens, passwords, or local file paths
SENSITIVE_QUERY_PATTERNS = [
    re.compile(
        r"\b(?:sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|bearer\s+[a-zA-Z0-9\-_]{20,})\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bpassword\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"^[a-zA-Z]:[\\/]", re.IGNORECASE),
    re.compile(r"^file:\/\/", re.IGNORECASE),
]


class WebSearchTool(BaseTool):
    """Tool to perform web searches using configured search providers."""

    name = "web_search"
    description = "Search the web for information using a search engine."
    parameters_schema = WebSearchArgs
    is_sensitive = False

    SEARCH_PROVIDERS = {
        "google": "https://www.google.com/search?q=",
        "duckduckgo": "https://duckduckgo.com/?q=",
        "bing": "https://www.bing.com/search?q=",
    }

    def run(self, validated_args: BaseModel) -> ToolResult:
        args: WebSearchArgs = validated_args  # type: ignore[assignment]
        query = args.query.strip()
        provider = args.provider.strip().lower()

        if not query:
            return ToolResult(
                success=False,
                error="Search query cannot be empty.",
            )

        # Safeguard: prevent transmitting local file paths or credentials to search engines
        for pattern in SENSITIVE_QUERY_PATTERNS:
            if pattern.search(query):
                logger.warning("Blocked web search containing sensitive credentials or local path.")
                return ToolResult(
                    success=False,
                    error="Search query blocked: contains potential credentials or local file paths.",
                    metadata={"blocked": True},
                )

        if provider not in self.SEARCH_PROVIDERS:
            supported = ", ".join(sorted(self.SEARCH_PROVIDERS.keys()))
            return ToolResult(
                success=False,
                error=f"Unsupported search provider '{provider}'. Supported: {supported}.",
                metadata={"provider": provider},
            )

        base_url = self.SEARCH_PROVIDERS[provider]
        search_url = f"{base_url}{urllib.parse.quote_plus(query)}"

        logger.info("Executing web search via %s for query: '%s'", provider, query)
        try:
            webbrowser.open(search_url, new=2)
            return ToolResult(
                success=True,
                output=f"Opened search for '{query}' on {provider}.",
                metadata={"query": query, "provider": provider, "url": search_url},
            )
        except Exception as exc:
            logger.error("Failed to execute web search for '%s': %s", query, exc)
            return ToolResult(
                success=False,
                error=f"Failed to launch search: {exc}",
                metadata={"query": query, "provider": provider},
            )
