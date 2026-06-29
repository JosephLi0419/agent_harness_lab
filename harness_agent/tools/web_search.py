"""Web search tools for the agent using DuckDuckGo."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_community.tools import DuckDuckGoSearchResults
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query")
    max_results: int = Field(default=5, description="Maximum number of search results")


@tool(args_schema=WebSearchInput)
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return results with reference links."""
    if not query.strip():
        return "Error: empty_query"

    max_results = max(1, min(max_results, 10))

    try:
        search = DuckDuckGoSearchResults(
            max_results=max_results,
            output_format="list",
        )
    except TypeError:
        try:
            search = DuckDuckGoSearchResults(output_format="list")
        except Exception as e:
            return f"Error initializing web search: {e}"
    except Exception as e:
        return f"Error initializing web search: {e}"

    try:
        results = search.invoke(query)
    except Exception as e:
        return f"Error searching web: {e}"

    return _format_results(results, max_results)


def _format_results(results: Any, max_results: int) -> str:
    """Format DuckDuckGo results so every item keeps its source URL visible."""
    if isinstance(results, str):
        return results

    if not isinstance(results, Sequence):
        return str(results)

    lines = []
    for index, item in enumerate(results[:max_results], 1):
        if not isinstance(item, dict):
            lines.append(f"{index}. {item}")
            continue

        title = item.get("title") or "Untitled"
        snippet = item.get("snippet") or item.get("body") or ""
        link = item.get("link") or item.get("href") or item.get("url") or ""

        lines.append(f"{index}. {title}")
        if snippet:
            lines.append(f"   {snippet}")
        if link:
            lines.append(f"   Source: {link}")

    return "\n".join(lines) if lines else "No results found."


WEB_SEARCH_TOOLS = [web_search]
