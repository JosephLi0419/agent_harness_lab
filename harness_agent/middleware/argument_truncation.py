"""Lightweight truncation of old tool-call arguments."""

from __future__ import annotations

from collections.abc import Sequence
from copy import deepcopy
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage

from .base import AgentMiddleware, AgentState

DEFAULT_TRIGGER_MESSAGES = 50
DEFAULT_KEEP_MESSAGES = 20
DEFAULT_MAX_LENGTH = 2_000


class ArgumentTruncationMiddleware(AgentMiddleware):
    """Truncate large tool-call arguments in older messages.

    This is a cheap preprocessing step before LLM-based compaction. It keeps
    recent messages intact, then trims long historical tool arguments such as
    write_file content or edit_file patches that rarely need to be replayed
    verbatim in future model calls.
    """

    name = "argument_truncation"

    def __init__(
        self,
        *,
        trigger_messages: int = DEFAULT_TRIGGER_MESSAGES,
        keep_messages: int = DEFAULT_KEEP_MESSAGES,
        max_length: int = DEFAULT_MAX_LENGTH,
    ):
        if trigger_messages < 1:
            raise ValueError("trigger_messages must be at least 1")
        if keep_messages < 0:
            raise ValueError("keep_messages must be non-negative")
        if max_length < 1:
            raise ValueError("max_length must be at least 1")

        self.trigger_messages = trigger_messages
        self.keep_messages = keep_messages
        self.max_length = max_length

    def before_model(
        self,
        messages: Sequence[AnyMessage],
        state: AgentState,
    ) -> Sequence[AnyMessage]:
        if len(messages) <= self.trigger_messages:
            return messages

        cutoff = max(0, len(messages) - self.keep_messages)
        old_messages = messages[:cutoff]
        recent_messages = messages[cutoff:]

        truncated_messages: list[AnyMessage] = []
        truncated_tool_calls = 0
        truncated_values = 0

        for message in old_messages:
            if not isinstance(message, AIMessage) or not message.tool_calls:
                truncated_messages.append(message)
                continue

            tool_calls, tool_call_count, value_count = _truncate_tool_calls(
                message.tool_calls,
                max_length=self.max_length,
            )
            additional_kwargs, additional_value_count = _truncate_value(
                message.additional_kwargs,
                max_length=self.max_length,
            )

            if tool_call_count == 0 and value_count == 0 and additional_value_count == 0:
                truncated_messages.append(message)
                continue

            truncated_messages.append(message.model_copy(update={
                "tool_calls": tool_calls,
                "additional_kwargs": additional_kwargs,
            }))
            truncated_tool_calls += tool_call_count
            truncated_values += value_count + additional_value_count

        if truncated_values:
            state["last_argument_truncation"] = {
                "messages_scanned": len(old_messages),
                "messages_kept_full": len(recent_messages),
                "tool_calls_truncated": truncated_tool_calls,
                "values_truncated": truncated_values,
                "max_length": self.max_length,
            }

        return truncated_messages + list(recent_messages)


def _truncate_tool_calls(
    tool_calls: list[dict[str, Any]],
    *,
    max_length: int,
) -> tuple[list[dict[str, Any]], int, int]:
    truncated_tool_calls: list[dict[str, Any]] = []
    changed_tool_calls = 0
    changed_values = 0

    for tool_call in tool_calls:
        truncated_tool_call, value_count = _truncate_value(
            tool_call,
            max_length=max_length,
        )
        truncated_tool_calls.append(truncated_tool_call)
        if value_count:
            changed_tool_calls += 1
            changed_values += value_count

    return truncated_tool_calls, changed_tool_calls, changed_values


def _truncate_value(value: Any, *, max_length: int) -> tuple[Any, int]:
    """Return a deep-copied value with long strings truncated."""
    if isinstance(value, str):
        if len(value) <= max_length:
            return value, 0
        omitted = len(value) - max_length
        return (
            f"{value[:max_length]}\n...[truncated {omitted} chars]",
            1,
        )

    if isinstance(value, dict):
        truncated: dict[Any, Any] = {}
        changed = 0
        for key, item in value.items():
            truncated_item, item_changed = _truncate_value(item, max_length=max_length)
            truncated[key] = truncated_item
            changed += item_changed
        return truncated, changed

    if isinstance(value, list):
        truncated_items = []
        changed = 0
        for item in value:
            truncated_item, item_changed = _truncate_value(item, max_length=max_length)
            truncated_items.append(truncated_item)
            changed += item_changed
        return truncated_items, changed

    if isinstance(value, tuple):
        truncated_items = []
        changed = 0
        for item in value:
            truncated_item, item_changed = _truncate_value(item, max_length=max_length)
            truncated_items.append(truncated_item)
            changed += item_changed
        return tuple(truncated_items), changed

    return deepcopy(value), 0
