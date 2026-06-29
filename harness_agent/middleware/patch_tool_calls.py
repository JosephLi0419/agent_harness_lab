"""Patch dangling tool calls before messages are sent to the model."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage

from .base import AgentMiddleware, AgentState


class PatchToolCallsMiddleware(AgentMiddleware):
    """Add cancellation ToolMessages for unresolved AIMessage tool calls.

    Some model providers require every AIMessage tool call to be followed by a
    ToolMessage with the matching tool_call_id. If a run is interrupted or a
    runtime drops a tool result, the next model call can fail. This middleware
    restores protocol validity by inserting explicit cancellation results for
    missing tool responses.
    """

    name = "patch_tool_calls"

    def __init__(
        self,
        *,
        cancellation_template: str = "Tool call {name} was cancelled",
    ):
        self.cancellation_template = cancellation_template

    def before_model(
        self,
        messages: Sequence[AnyMessage],
        state: AgentState,
    ) -> Sequence[AnyMessage]:
        patched: list[AnyMessage] = []
        patched_records: list[dict[str, str]] = []
        index = 0

        while index < len(messages):
            message = messages[index]
            patched.append(message)

            if not _has_tool_calls(message):
                index += 1
                continue

            index += 1
            present_tool_call_ids: set[str] = set()

            while index < len(messages) and isinstance(messages[index], ToolMessage):
                tool_message = messages[index]
                if tool_message.tool_call_id:
                    present_tool_call_ids.add(tool_message.tool_call_id)
                patched.append(tool_message)
                index += 1

            for tool_call in message.tool_calls:
                tool_call_id = _tool_call_id(tool_call)
                if not tool_call_id or tool_call_id in present_tool_call_ids:
                    continue

                tool_name = _tool_call_name(tool_call)
                patched.append(ToolMessage(
                    content=self.cancellation_template.format(name=tool_name),
                    tool_call_id=tool_call_id,
                ))
                patched_records.append({
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                })

        if patched_records:
            state["last_patched_tool_calls"] = patched_records

        return patched


def _has_tool_calls(message: AnyMessage) -> bool:
    return isinstance(message, AIMessage) and bool(message.tool_calls)


def _tool_call_id(tool_call: Any) -> str | None:
    if isinstance(tool_call, dict):
        value = tool_call.get("id")
    else:
        value = getattr(tool_call, "id", None)
    return str(value) if value else None


def _tool_call_name(tool_call: Any) -> str:
    if isinstance(tool_call, dict):
        value = tool_call.get("name")
    else:
        value = getattr(tool_call, "name", None)
    return str(value) if value else "unknown"
