"""Conversation compaction middleware."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately

from .base import AgentMiddleware, AgentState

COMPACT_THRESHOLD = 50_000
KEEP_GROUPS = 10
KEEP_TOKEN_BUDGET = 12_000

_SUMMARY_PROMPT = """Summarize the earlier conversation history.

Focus on:
1. Decisions and findings
2. Files, tools, and sources already checked
3. Current state of the work
4. Pending items and blockers

Keep it concise but complete enough for the agent to continue.

---
{history}
"""


class CompactMiddleware(AgentMiddleware):
    """Summarize older messages once the conversation grows too large."""

    name = "compact"

    def __init__(
        self,
        llm: Any,
        *,
        threshold: int = COMPACT_THRESHOLD,
        keep_groups: int = KEEP_GROUPS,
        keep_token_budget: int = KEEP_TOKEN_BUDGET,
    ):
        self.llm = llm
        self.threshold = threshold
        self.keep_groups = keep_groups
        self.keep_token_budget = keep_token_budget

    def before_model(
        self,
        messages: Sequence[AnyMessage],
        state: AgentState,
    ) -> Sequence[AnyMessage]:
        total = count_tokens_approximately(messages)
        if total < self.threshold:
            state["last_compaction"] = None
            return messages

        groups = _message_groups(list(messages))
        keep_groups = _select_keep_groups(
            groups,
            max_groups=self.keep_groups,
            token_budget=self.keep_token_budget,
        )
        keep = _flatten(keep_groups)
        to_summarize = _flatten(groups[:len(groups) - len(keep_groups)])

        if not to_summarize:
            state["last_compaction"] = None
            return messages

        history_text = "\n".join(
            f"{message.__class__.__name__}: {_message_text(message)[:300]}"
            for message in to_summarize
        )
        response = self.llm.invoke([
            HumanMessage(content=_SUMMARY_PROMPT.format(history=history_text))
        ])
        summary = HumanMessage(
            content=(
                f"[Context summary: {len(to_summarize)} earlier messages compacted]\n"
                f"{response.content}"
            )
        )

        state["last_compaction"] = {
            "compacted_messages": len(to_summarize),
            "original_tokens": total,
            "kept_tokens": count_tokens_approximately(keep),
        }
        return [summary] + list(keep)


def _message_text(message: AnyMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    if isinstance(message.content, list):
        return " ".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in message.content
        )
    return str(message.content)


def _message_groups(messages: list[AnyMessage]) -> list[list[AnyMessage]]:
    groups: list[list[AnyMessage]] = []
    index = 0

    while index < len(messages):
        message = messages[index]
        group = [message]

        if isinstance(message, AIMessage) and message.tool_calls:
            index += 1
            while index < len(messages) and isinstance(messages[index], ToolMessage):
                group.append(messages[index])
                index += 1
            groups.append(group)
            continue

        if isinstance(message, ToolMessage):
            index += 1
            while index < len(messages) and isinstance(messages[index], ToolMessage):
                group.append(messages[index])
                index += 1
            groups.append(group)
            continue

        groups.append(group)
        index += 1

    return groups


def _select_keep_groups(
    groups: list[list[AnyMessage]],
    *,
    max_groups: int,
    token_budget: int,
) -> list[list[AnyMessage]]:
    keep: list[list[AnyMessage]] = []
    token_count = 0

    for group in reversed(groups):
        if _starts_with_orphan_tool(group):
            break

        group_tokens = count_tokens_approximately(group)
        if keep and token_count + group_tokens > token_budget:
            break
        if keep and len(keep) >= max_groups:
            break
        if not keep and group_tokens > token_budget and _contains_tool_message(group):
            break

        keep.insert(0, group)
        token_count += group_tokens

    return keep


def _starts_with_orphan_tool(group: list[AnyMessage]) -> bool:
    return bool(group) and isinstance(group[0], ToolMessage)


def _contains_tool_message(group: list[AnyMessage]) -> bool:
    return any(isinstance(message, ToolMessage) for message in group)


def _flatten(groups: list[list[AnyMessage]]) -> list[AnyMessage]:
    return [message for group in groups for message in group]
