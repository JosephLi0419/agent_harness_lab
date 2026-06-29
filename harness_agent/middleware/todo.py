"""Todo-list middleware for complex multi-step agent work."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from .base import AgentMiddleware, AgentState, append_to_system

TodoStatus = Literal["pending", "in_progress", "done", "blocked"]


class TodoItemInput(BaseModel):
    """One todo item maintained by TodoListMiddleware."""

    task: str = Field(description="Concrete task the agent needs to complete")
    status: TodoStatus = Field(
        default="pending",
        description="Current task status: pending, in_progress, done, or blocked",
    )
    id: str | None = Field(
        default=None,
        description="Stable id such as task-1. Omit to let the middleware assign one.",
    )


class WriteTodoListInput(BaseModel):
    """Replace the current todo list with the latest agent-maintained list."""

    todos: list[TodoItemInput] = Field(
        description="Full current todo list. Include completed tasks as done."
    )


class TodoListMiddleware(AgentMiddleware):
    """Maintain a todo list in agent state and expose a tool for updates.

    This middleware is meant to be first in the stack. It initializes state,
    injects the current todo list plus operating rules into the system prompt,
    and provides a `write_todo_list` tool that the model can call to update
    state during long-running tasks.
    """

    name = "todo_list"

    def __init__(
        self,
        *,
        state_key: str = "todo_list",
        tool_name: str = "write_todo_list",
        require_for_complex_tasks: bool = True,
    ):
        self.state_key = state_key
        self.tool_name = tool_name
        self.require_for_complex_tasks = require_for_complex_tasks

    def before_agent(self, state: AgentState) -> AgentState | None:
        if self.state_key in state:
            return None
        return {self.state_key: []}

    def inject_system(self, system: str, state: AgentState) -> str:
        todos = normalize_todos(state.get(self.state_key, []))
        current_list = render_todos(todos)
        requirement = (
            "For complex or multi-step requests, call the todo tool before "
            "doing substantive work."
            if self.require_for_complex_tasks
            else "Use the todo tool when it would help track the work."
        )

        instructions = f"""<todo_list_middleware>
Current todo list:
{current_list}

Rules:
- {requirement}
- Keep the list short, concrete, and ordered by execution sequence.
- Use `{self.tool_name}` with the full current list whenever you create, reorder, or update tasks.
- Mark a task `in_progress` when you start it.
- Mark a task `done` immediately after completing it.
- Use `blocked` only when progress truly depends on user input or an unavailable external condition.
- Before the final answer, verify that every non-blocked task is `done`; mention any blocked tasks clearly.
- Simple one-step replies do not need a todo list.
</todo_list_middleware>"""
        return append_to_system(system, instructions)

    def tools(self, state: AgentState) -> list[Any]:
        def write_todo_list(todos: list[TodoItemInput]) -> str:
            normalized = normalize_todos(todos)
            state[self.state_key] = normalized
            return f"Todo list updated.\n{render_todos(normalized)}"

        return [
            StructuredTool.from_function(
                func=write_todo_list,
                name=self.tool_name,
                description=(
                    "Create or replace the full todo list for the current task. "
                    "Call this before complex work, after completing each task, "
                    "and before finalizing if anything changed."
                ),
                args_schema=WriteTodoListInput,
            )
        ]

    def is_complete(self, state: AgentState) -> bool:
        """Return True when all todos are done or the list is empty."""
        todos = normalize_todos(state.get(self.state_key, []))
        return all(todo["status"] == "done" for todo in todos)

    def open_items(self, state: AgentState) -> list[dict[str, str]]:
        """Return todo items that are not done."""
        todos = normalize_todos(state.get(self.state_key, []))
        return [todo for todo in todos if todo["status"] != "done"]


def normalize_todos(raw_todos: Any) -> list[dict[str, str]]:
    """Return a stable, serializable todo list."""
    if not raw_todos:
        return []

    normalized: list[dict[str, str]] = []
    for index, raw in enumerate(raw_todos, 1):
        item = _coerce_todo(raw)
        task = item.get("task", "").strip()
        if not task:
            continue

        status = item.get("status", "pending")
        if status == "completed":
            status = "done"
        if status not in {"pending", "in_progress", "done", "blocked"}:
            status = "pending"

        normalized.append({
            "id": item.get("id") or f"task-{index}",
            "task": task,
            "status": status,
        })

    return normalized


def render_todos(todos: Any) -> str:
    """Render todos as a compact checklist for prompt injection or tool output."""
    normalized = normalize_todos(todos)
    if not normalized:
        return "(empty)"

    markers = {
        "pending": "[ ]",
        "in_progress": "[>]",
        "done": "[x]",
        "blocked": "[!]",
    }
    return "\n".join(
        f"{markers[todo['status']]} {todo['id']}: {todo['task']} ({todo['status']})"
        for todo in normalized
    )


def _coerce_todo(raw: Any) -> dict[str, str]:
    if isinstance(raw, BaseModel):
        raw = raw.model_dump()
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items() if value is not None}
    return {"task": str(raw), "status": "pending"}
