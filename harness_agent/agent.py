"""LangGraph agent runtime wired to the middleware stack."""

from __future__ import annotations

import time
from typing import Annotated, Any, TypedDict

import httpx
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langgraph.config import get_stream_writer
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from openai import APIConnectionError, APITimeoutError, BadRequestError

from .middleware import (
    DEFAULT_SKILL_ID,
    MiddlewareStack,
    SkillsMiddleware,
    build_default_middleware_stack,
    request_approval,
)
from .tools.datetime import DATETIME_TOOLS
from .tools.filesystem import FILESYSTEM_TOOLS, HIGH_RISK_TOOLS
from .tools.web_fetch import WEB_FETCH_TOOLS
from .tools.web_search import WEB_SEARCH_TOOLS


class AgentState(TypedDict, total=False):
    """LangGraph state shared by the runtime and middleware."""

    messages: Annotated[list[AnyMessage], add_messages]
    active_skills: list[str]
    pinned_skills: list[str]
    active_domain: str
    writes_approved: bool
    todo_list: list[dict[str, str]]
    global_memory_loaded: bool
    global_memory: str
    domain_memory_files: dict[str, str]
    last_argument_truncation: dict[str, Any]
    last_compaction: dict[str, Any]
    last_patched_tool_calls: list[dict[str, str]]
    last_skill_route_user_text: str
    context_window: dict[str, Any]
    context_window_events: list[dict[str, Any]]


BASE_TOOLS = [*FILESYSTEM_TOOLS, *WEB_SEARCH_TOOLS, *WEB_FETCH_TOOLS, *DATETIME_TOOLS]
MODEL_RETRY_ATTEMPTS = 2
MODEL_RETRY_INITIAL_DELAY_SECONDS = 0.75
TRANSIENT_MODEL_ERRORS = (APIConnectionError, APITimeoutError, httpx.TransportError)
MIDDLEWARE_STATE_KEYS = (
    "active_skills",
    "pinned_skills",
    "domain_memory_files",
    "last_argument_truncation",
    "last_compaction",
    "last_patched_tool_calls",
    "last_skill_route_user_text",
    "context_window",
    "context_window_events",
)


def build_graph(
    llm: Any,
    *,
    domain: str | None = None,
    system_prompt: str | None = None,
    middleware_stack: MiddlewareStack | None = None,
    skills_middleware: SkillsMiddleware | None = None,
    include_memory: bool = True,
    include_skills: bool = True,
    include_argument_truncation: bool = True,
    include_compact: bool = True,
) -> Any:
    """Build and compile the LangGraph agent graph.

    The middleware stack owns cross-cutting behavior such as todo tracking,
    dangling tool-call patching, argument truncation, memory, and compaction.
    """
    skills = skills_middleware or SkillsMiddleware(fallback_skill_id=domain, router_llm=llm)
    stack = middleware_stack or build_default_middleware_stack(
        llm=llm,
        domain=domain,
        skills_middleware=skills,
        include_memory=include_memory,
        include_skills=include_skills,
        include_argument_truncation=include_argument_truncation,
        include_compact=include_compact,
    )
    base_system_prompt = system_prompt if system_prompt is not None else skills.base_prompt

    def tools_for_state(state: AgentState) -> list[Any]:
        return [*BASE_TOOLS, *stack.tools(state)]

    def agent_node(state: AgentState) -> dict[str, Any]:
        working_state: AgentState = {**state}
        updates: dict[str, Any] = {}

        init_updates = stack.before_agent(working_state)
        if init_updates:
            updates.update(init_updates)
            working_state.update(init_updates)
            if init_updates.get("global_memory_loaded"):
                _emit_runtime_event({
                    "event": "memory_loaded",
                    "keys": ["global_memory_loaded"],
                })

        messages = stack.before_model(working_state.get("messages", []), working_state)
        system = stack.inject_system(base_system_prompt, working_state)
        for key in MIDDLEWARE_STATE_KEYS:
            if key in working_state:
                updates[key] = working_state[key]
        bound_tools = tools_for_state(working_state)
        _emit_runtime_event({
            "event": "skills_selected",
            "active_skills": working_state.get("active_skills", []),
        })
        _emit_runtime_event({
            "event": "tools_bound",
            "tools": [_tool_name(tool) for tool in bound_tools],
        })
        _emit_runtime_event({"event": "model_start"})
        model = llm.bind_tools(bound_tools)

        try:
            response = _invoke_model_with_retry(model, [SystemMessage(content=system), *messages])
        except BadRequestError as e:
            error_detail = _extract_content_filter_reason(e)
            response = AIMessage(
                content=(
                    "Request blocked by the LLM provider: "
                    f"{error_detail}\nTry rephrasing your last message or starting a new session."
                )
            )
        except TRANSIENT_MODEL_ERRORS as e:
            _emit_runtime_event({
                "event": "model_error",
                "error_type": type(e).__name__,
                "retryable": True,
            })
            response = AIMessage(content=_format_transient_model_error(e))

        updates["messages"] = [response]
        if response.tool_calls:
            _emit_runtime_event({
                "event": "tool_plan",
                "tool_calls": response.tool_calls,
            })
        else:
            _emit_runtime_event({"event": "model_done"})
        return updates

    def tool_node_with_hitl(state: AgentState) -> dict[str, Any]:
        """Execute tools, asking once per session before high-risk tool calls."""
        messages = state.get("messages", [])
        if not messages:
            return {"messages": []}

        last = messages[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {"messages": []}

        writes_approved = state.get("writes_approved", False)
        safe_calls = [
            tool_call for tool_call in last.tool_calls
            if tool_call.get("name") not in HIGH_RISK_TOOLS or writes_approved
        ]
        risky_calls = [
            tool_call for tool_call in last.tool_calls
            if tool_call.get("name") in HIGH_RISK_TOOLS and not writes_approved
        ]

        tool_messages: list[ToolMessage] = []
        state_updates: dict[str, Any] = {}
        all_tools = tools_for_state(state)

        if safe_calls:
            _emit_runtime_event({"event": "tool_start", "tool_calls": safe_calls})
            tool_messages.extend(_run_tool_calls(all_tools, messages, safe_calls))
            _emit_runtime_event({"event": "tool_result", "messages": tool_messages})
            _emit_todo_list_if_updated(safe_calls, state)

        if risky_calls:
            _emit_runtime_event({"event": "approval_required", "tool_calls": risky_calls})
            if request_approval(risky_calls):
                state_updates["writes_approved"] = True
                _emit_runtime_event({"event": "approval_result", "approved": True})
                _emit_runtime_event({"event": "tool_start", "tool_calls": risky_calls})
                tool_messages.extend(_run_tool_calls(all_tools, messages, risky_calls))
                _emit_runtime_event({"event": "tool_result", "messages": tool_messages})
                _emit_todo_list_if_updated(risky_calls, state)
            else:
                _emit_runtime_event({"event": "approval_result", "approved": False})
                tool_messages.extend(_rejected_tool_messages(risky_calls))

        if "todo_list" in state:
            state_updates["todo_list"] = state["todo_list"]
        if "active_skills" in state:
            state_updates["active_skills"] = state["active_skills"]
        if "pinned_skills" in state:
            state_updates["pinned_skills"] = state["pinned_skills"]

        return {"messages": tool_messages, **state_updates}

    # ------------------------------------------------------------------ #
    # Graph assembly                                                       #
    # ------------------------------------------------------------------ #

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node_with_hitl)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=MemorySaver())


def load_system_prompt(domain: str | None = None) -> str:
    """Load SOUL plus a selected skill prompt.

    Kept for compatibility with the earlier build-time domain API.
    """
    skills = SkillsMiddleware(fallback_skill_id=domain or DEFAULT_SKILL_ID)
    skill_ids = skills.select_skill_ids(
        {"active_skills": [domain]} if domain else {},
        fallback_skill_id=domain or DEFAULT_SKILL_ID,
    )
    return skills.render_system_prompt(skill_ids)


def _run_tool_calls(
    tools: list[Any],
    messages: list[AnyMessage],
    tool_calls: list[dict[str, Any]],
) -> list[ToolMessage]:
    tool_node = ToolNode(tools)
    tool_message = AIMessage(content="", tool_calls=tool_calls)
    result = tool_node.invoke({"messages": [*messages[:-1], tool_message]})
    return list(result.get("messages", []))


def _rejected_tool_messages(tool_calls: list[dict[str, Any]]) -> list[ToolMessage]:
    messages: list[ToolMessage] = []
    for tool_call in tool_calls:
        tool_call_id = tool_call.get("id")
        if not tool_call_id:
            continue
        messages.append(ToolMessage(
            content="Tool call rejected by user.",
            tool_call_id=tool_call_id,
        ))
    return messages


def _invoke_model_with_retry(model: Any, messages: list[AnyMessage]) -> AIMessage:
    """Retry once for transient provider transport failures."""
    for attempt in range(1, MODEL_RETRY_ATTEMPTS + 1):
        try:
            return model.invoke(messages)
        except TRANSIENT_MODEL_ERRORS as e:
            if attempt >= MODEL_RETRY_ATTEMPTS:
                raise
            delay = MODEL_RETRY_INITIAL_DELAY_SECONDS * attempt
            _emit_runtime_event({
                "event": "model_retry",
                "error_type": type(e).__name__,
                "attempt": attempt,
                "max_attempts": MODEL_RETRY_ATTEMPTS,
                "delay_seconds": delay,
            })
            time.sleep(delay)

    raise RuntimeError("Model retry loop exhausted unexpectedly.")


def _emit_todo_list_if_updated(tool_calls: list[dict[str, Any]], state: AgentState) -> None:
    if not any(tool_call.get("name") == "write_todo_list" for tool_call in tool_calls):
        return
    _emit_runtime_event({
        "event": "todo_list",
        "todos": state.get("todo_list", []),
    })


def _extract_content_filter_reason(e: BadRequestError) -> str:
    """Pull a human-readable reason out of an Azure content filter error."""
    try:
        body = e.response.json()
        inner = body["error"].get("innererror", {})
        result = inner.get("content_filter_result", {})
        triggered = [
            f"{category}({info['severity']})"
            for category, info in result.items()
            if info.get("filtered")
        ]
        return f"content filter triggered - {', '.join(triggered)}" if triggered else str(e)
    except Exception:
        return str(e)


def _format_transient_model_error(e: BaseException) -> str:
    """Return a user-facing message for retryable model transport failures."""
    detail = str(e).strip() or "connection interrupted"
    return (
        "The LLM provider connection was interrupted before the response completed "
        f"({type(e).__name__}: {detail}).\n"
        "Please retry your request. If this keeps happening, check the network, "
        "provider endpoint, or try another provider/model."
    )


def _emit_runtime_event(payload: dict[str, Any]) -> None:
    """Emit a custom LangGraph stream event when streaming is enabled."""
    try:
        writer = get_stream_writer()
    except RuntimeError:
        return
    writer(payload)


def _tool_name(tool: Any) -> str:
    return str(getattr(tool, "name", None) or getattr(tool, "__name__", type(tool).__name__))
