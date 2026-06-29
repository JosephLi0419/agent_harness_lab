"""Middleware exports and default stack factory."""

from __future__ import annotations

from typing import Any

from .argument_truncation import ArgumentTruncationMiddleware
from .base import AgentMiddleware, AgentState, MiddlewareStack, append_to_system
from .compact import CompactMiddleware
from .hitl import HumanApprovalMiddleware, request_approval
from .memory import MemoryMiddleware, ensure_memory_files
from .patch_tool_calls import PatchToolCallsMiddleware
from .skills import DEFAULT_SKILL_ID, Skill, SkillsMiddleware
from .todo import TodoListMiddleware, normalize_todos, render_todos


def build_default_middleware_stack(
    *,
    llm: Any | None = None,
    domain: str | None = None,
    skills_middleware: SkillsMiddleware | None = None,
    include_memory: bool = True,
    include_skills: bool = True,
    include_argument_truncation: bool = True,
    include_compact: bool = True,
) -> MiddlewareStack:
    """Build the default stack.

    TodoListMiddleware intentionally comes first so planning state is available
    before memory and compaction add their own context.
    """
    middlewares: list[AgentMiddleware] = [
        TodoListMiddleware(),
    ]

    if include_skills:
        middlewares.append(skills_middleware or SkillsMiddleware(fallback_skill_id=domain))

    middlewares.append(PatchToolCallsMiddleware())

    if include_argument_truncation:
        middlewares.append(ArgumentTruncationMiddleware())

    if include_memory:
        ensure_memory_files(domain)
        middlewares.append(MemoryMiddleware(domain=domain))

    if include_compact and llm is not None:
        middlewares.append(CompactMiddleware(llm))

    return MiddlewareStack(middlewares)


__all__ = [
    "AgentMiddleware",
    "AgentState",
    "ArgumentTruncationMiddleware",
    "CompactMiddleware",
    "HumanApprovalMiddleware",
    "MemoryMiddleware",
    "MiddlewareStack",
    "PatchToolCallsMiddleware",
    "Skill",
    "SkillsMiddleware",
    "TodoListMiddleware",
    "append_to_system",
    "build_default_middleware_stack",
    "DEFAULT_SKILL_ID",
    "ensure_memory_files",
    "normalize_todos",
    "render_todos",
    "request_approval",
]
