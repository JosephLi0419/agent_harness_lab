"""Composable middleware primitives for the agent runtime.

The runtime owns the conversation loop. Middleware owns cross-cutting behavior:
state initialization, prompt injection, message rewriting, and optional tools.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from langchain_core.messages import AnyMessage

AgentState = dict[str, Any]


class AgentMiddleware:
    """Base class for middleware components.

    Subclasses can override only the hooks they need. Hooks are intentionally
    small and explicit so the agent runner can stay independent from each
    middleware's implementation details.
    """

    name = "middleware"

    def before_agent(self, state: AgentState) -> AgentState | None:
        """Run once before the agent starts. Return state updates or None."""
        return None

    def before_model(
        self,
        messages: Sequence[AnyMessage],
        state: AgentState,
    ) -> Sequence[AnyMessage]:
        """Run before each model call. Return the messages to send."""
        return messages

    def inject_system(self, system: str, state: AgentState) -> str:
        """Run before each model call. Return the system prompt to send."""
        return system

    def tools(self, state: AgentState) -> list[Any]:
        """Return runtime tools exposed by this middleware, if any."""
        return []


class MiddlewareStack:
    """Ordered collection of middleware with deterministic hook execution."""

    def __init__(self, middlewares: Iterable[AgentMiddleware] | None = None):
        self._middlewares = list(middlewares or [])

    @property
    def middlewares(self) -> tuple[AgentMiddleware, ...]:
        """Return middleware in execution order."""
        return tuple(self._middlewares)

    def before_agent(self, state: AgentState) -> AgentState:
        """Run startup hooks in order and return the merged state updates."""
        updates: AgentState = {}
        working_state: AgentState = {**state}

        for middleware in self._middlewares:
            result = middleware.before_agent(working_state)
            if not result:
                continue
            updates.update(result)
            working_state.update(result)

        return updates

    def before_model(
        self,
        messages: Sequence[AnyMessage],
        state: AgentState,
    ) -> list[AnyMessage]:
        """Run message preparation hooks in order."""
        prepared: Sequence[AnyMessage] = messages
        for middleware in self._middlewares:
            prepared = middleware.before_model(prepared, state)
        return list(prepared)

    def inject_system(self, system: str, state: AgentState) -> str:
        """Run system prompt injection hooks in order."""
        prepared = system
        for middleware in self._middlewares:
            prepared = middleware.inject_system(prepared, state)
        return prepared

    def tools(self, state: AgentState) -> list[Any]:
        """Collect tools exposed by middleware in stack order."""
        runtime_tools: list[Any] = []
        for middleware in self._middlewares:
            runtime_tools.extend(middleware.tools(state))
        return runtime_tools

    def names(self) -> list[str]:
        """Return middleware names in execution order."""
        return [middleware.name for middleware in self._middlewares]


def append_to_system(system: str, text: str) -> str:
    """Append text to a system prompt, separated by one blank line."""
    if not text:
        return system
    return f"{system}\n\n{text}" if system else text
