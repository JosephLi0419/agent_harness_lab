"""Date and time tools for the agent."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class DateTimeInput(BaseModel):
    timezone: str = Field(
        default="Asia/Taipei",
        description=(
            "IANA timezone for the user's requested location, such as "
            "Asia/Taipei, Asia/Tokyo, Europe/London, or America/New_York."
        ),
    )
    location: str | None = Field(
        default=None,
        description="Optional human-readable location label from the user request.",
    )


@tool(args_schema=DateTimeInput)
def get_datetime(timezone: str = "Asia/Taipei", location: str | None = None) -> dict[str, str]:
    """Get the current local date and time for a requested IANA timezone.

    Use this before interpreting relative dates like today, tomorrow, or
    yesterday. Choose the timezone from the user's requested location when it is
    clear. If the location is ambiguous, ask the user or use Asia/Taipei as the
    default personal timezone.
    """
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return {
            "error": "unknown_timezone",
            "timezone": timezone,
            "hint": "Use a valid IANA timezone such as Asia/Taipei or America/New_York.",
        }

    now = datetime.now(tz)
    result = {
        "timezone": timezone,
        "date": now.date().isoformat(),
        "time": now.strftime("%H:%M:%S"),
        "datetime": now.isoformat(timespec="seconds"),
        "weekday": now.strftime("%A"),
        "utc_offset": now.strftime("%z"),
    }
    if location:
        result["location"] = location
    return result


DATETIME_TOOLS = [get_datetime]
