"""Web fetch tool for extracting readable webpage text with trafilatura."""

from __future__ import annotations

from urllib.parse import urlparse

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class WebFetchInput(BaseModel):
    url: str = Field(description="HTTP or HTTPS URL to fetch")
    max_chars: int = Field(
        default=12000,
        description="Maximum number of extracted characters to return",
    )


@tool(args_schema=WebFetchInput)
def web_fetch(url: str, max_chars: int = 12000) -> str:
    """Fetch a web page and extract its main readable content."""
    normalized_url = url.strip()
    if not normalized_url:
        return "Error: empty_url"

    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return f"Error: invalid_url: {url}"

    max_chars = max(1000, min(max_chars, 30000))

    try:
        import trafilatura
    except ImportError:
        return "Error: missing_dependency: install trafilatura to use web_fetch"

    try:
        downloaded = trafilatura.fetch_url(normalized_url)
    except Exception as e:
        return f"Error fetching URL: {e}"

    if not downloaded:
        return f"Error: fetch_failed: {normalized_url}"

    try:
        extracted = trafilatura.extract(
            downloaded,
            url=normalized_url,
            include_comments=False,
            include_tables=True,
            include_links=True,
        )
    except Exception as e:
        return f"Error extracting webpage content: {e}"

    if not extracted:
        return f"Error: no_readable_content: {normalized_url}"

    content = extracted.strip()
    header = f"Source: {normalized_url}\n\n"
    budget = max_chars - len(header)
    if budget <= 0:
        return header.strip()

    if len(content) > budget:
        truncation_note = (
            f"\n\n[Output truncated at {max_chars} characters. "
            "Call web_fetch with a higher max_chars value if more detail is needed.]"
        )
        content_budget = max(0, budget - len(truncation_note))
        content = (
            content[:content_budget].rstrip()
            + truncation_note
        )

    return header + content


WEB_FETCH_TOOLS = [web_fetch]
