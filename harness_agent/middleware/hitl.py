"""Human-in-the-loop approval helpers for risky tool calls."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .base import AgentMiddleware


class HumanApprovalMiddleware(AgentMiddleware):
    """Prompt the user before risky tool calls are executed.

    This middleware exposes an explicit approval method because different agent
    runners represent tool calls differently. The runner can call
    `filter_tool_calls` before dispatching tools.
    """

    name = "human_approval"

    def __init__(
        self,
        *,
        high_risk_tools: Iterable[str],
        approve_once: bool = True,
    ):
        self.high_risk_tools = set(high_risk_tools)
        self.approve_once = approve_once
        self._approved = False

    def filter_tool_calls(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return (approved_calls, rejected_calls)."""
        risky = [
            call for call in tool_calls
            if call.get("name") in self.high_risk_tools and not self._approved
        ]
        safe = [
            call for call in tool_calls
            if call.get("name") not in self.high_risk_tools or self._approved
        ]

        if not risky:
            return safe, []

        approved = request_approval(risky)
        if approved:
            if self.approve_once:
                self._approved = True
            return safe + risky, []

        return safe, risky


def request_approval(tool_calls: list[dict[str, Any]]) -> bool:
    """Ask the user to approve risky tool calls."""
    print()
    print("Approval required: the agent wants to run high-risk tools.")

    for index, tool_call in enumerate(tool_calls, 1):
        name = tool_call.get("name", "unknown")
        args = tool_call.get("args", {})
        print(f"\n{index}. {name}")

        if isinstance(args, dict):
            for label, key in (
                ("Path", "file_path"),
                ("Source", "source_path"),
                ("Destination", "destination_path"),
            ):
                if key in args:
                    print(f"   {label}: {args[key]}")

    while True:
        choice = input("\nApprove all? (yes/no): ").strip().lower()
        if choice in {"y", "yes"}:
            return True
        if choice in {"n", "no"}:
            return False
        print("Please enter yes or no.")
