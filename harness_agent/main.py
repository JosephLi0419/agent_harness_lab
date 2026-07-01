"""CLI entry point for the Harness Agent."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from rich.console import Console
from rich.markup import escape
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .agent import build_graph
from .llm.providers import (
    CONFIG_PATH,
    Provider,
    create_llm,
    ensure_config_exists,
    get_default_provider,
    load_config,
)
from .middleware import SkillsMiddleware
from .middleware.memory import DOMAIN_MEMORY_DIR, GLOBAL_MEMORY_FILE, MEMORY_DIR, ensure_memory_files

PROVIDERS = ("azure", "ollama")
EXIT_COMMANDS = {"exit", "quit", "q", "bye"}
console = Console()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Harness Agent CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        return args.func(args)
    except KeyboardInterrupt:
        console.print("\n[dim]Session ended.[/dim]")
        return 130


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-harness-lab",
        description="Harness Agent - a skill-driven LangGraph assistant.",
    )
    subcommands = parser.add_subparsers(dest="command")

    chat = subcommands.add_parser("chat", help="Start an interactive chat session.")
    _add_runtime_options(chat)
    chat.set_defaults(func=_chat_command)

    ask = subcommands.add_parser("ask", help="Run one prompt and print the answer.")
    ask.add_argument("prompt", help="Prompt to send to the agent.")
    _add_runtime_options(ask)
    ask.set_defaults(func=_ask_command)

    skills = subcommands.add_parser("skills", help="List available skills.")
    skills.set_defaults(func=_skills_command)

    config = subcommands.add_parser("config", help="Show provider, memory, and skill paths.")
    config.set_defaults(func=_config_command)

    return parser


def _add_runtime_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provider",
        choices=PROVIDERS,
        default=None,
        help="LLM provider to use. Defaults to config/env auto-detection.",
    )
    parser.add_argument(
        "--domain",
        default=None,
        help="Fallback skill/domain id, such as stock_research or weather.",
    )
    parser.add_argument(
        "--skill",
        action="append",
        default=None,
        help="Explicit active skill. Can be passed more than once.",
    )
    parser.add_argument(
        "--thread-id",
        default=None,
        help="LangGraph checkpoint thread id. Defaults to a provider/domain-based id.",
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Disable memory loading and memory prompt injection.",
    )
    parser.add_argument(
        "--no-compact",
        action="store_true",
        help="Disable context compaction.",
    )


def _chat_command(args: argparse.Namespace) -> int:
    app, config, initial_state, skills = _setup_runtime(args)

    console.print(Panel.fit(
        "\n".join([
            "[bold cyan]Harness Agent[/bold cyan]",
            f"[bold]Provider:[/bold] {_provider_label(args.provider)}",
            f"[bold]Thread:[/bold] {config['configurable']['thread_id']}",
            f"[bold]Memory:[/bold] {GLOBAL_MEMORY_FILE}",
            "[dim]Type 'exit' to quit. Use '/skill <name>' to switch skills.[/dim]",
        ]),
        border_style="cyan",
    ))

    first = True
    while True:
        if first:
            user_text = console.input("[bold green]You:[/bold green] ").strip()
            first = False
        else:
            user_text = console.input("\n[bold green]You:[/bold green] ").strip()

        if user_text.lower() in EXIT_COMMANDS:
            break
        if not user_text:
            continue

        state = {**initial_state, "messages": [HumanMessage(content=user_text)]}
        _run_turn(app, state, config, skills)
        initial_state = {}

    console.print("[dim]Session ended.[/dim]")
    return 0


def _ask_command(args: argparse.Namespace) -> int:
    app, config, initial_state, skills = _setup_runtime(args)
    state = {**initial_state, "messages": [HumanMessage(content=args.prompt)]}
    _run_turn(app, state, config, skills)
    return 0


def _skills_command(args: argparse.Namespace) -> int:
    skills = SkillsMiddleware()

    table = Table(title="Available Skills", header_style="bold cyan")
    table.add_column("Skill", style="bold")
    table.add_column("Name")
    table.add_column("Aliases", style="dim")
    table.add_column("Triggers", style="dim")
    for skill in skills.list_skills():
        aliases = ", ".join(skill.aliases) if skill.aliases else "-"
        triggers = ", ".join(skill.triggers[:8]) if skill.triggers else "-"
        if len(skill.triggers) > 8:
            triggers += ", ..."
        table.add_row(skill.id, skill.name, aliases, triggers)
    console.print(table)
    return 0


def _config_command(args: argparse.Namespace) -> int:
    ensure_config_exists()
    config = load_config()
    skills = SkillsMiddleware()

    table = Table(title="Harness Agent Config", header_style="bold cyan")
    table.add_column("Key", style="bold")
    table.add_column("Value")
    table.add_row("Config", str(CONFIG_PATH))
    table.add_row("Provider", str(get_default_provider()))
    if config.get("llm", {}).get("model"):
        table.add_row("Model", str(config["llm"]["model"]))
    table.add_row("Memory dir", str(MEMORY_DIR))
    table.add_row("Global mem", str(GLOBAL_MEMORY_FILE))
    table.add_row("Domain mem", str(DOMAIN_MEMORY_DIR))
    table.add_row("Skills dir", str(skills.skills_dir))
    table.add_row("Skills", ", ".join(skill.id for skill in skills.list_skills()))
    console.print(table)
    return 0


def _setup_runtime(
    args: argparse.Namespace,
) -> tuple[Any, dict[str, Any], dict[str, Any], SkillsMiddleware]:
    provider = _provider_arg(args.provider)
    ensure_config_exists(provider)
    ensure_memory_files(args.domain)

    llm = create_llm(provider=provider)
    skills_middleware = SkillsMiddleware(fallback_skill_id=args.domain)
    app = build_graph(
        llm,
        domain=args.domain,
        skills_middleware=skills_middleware,
        include_memory=not args.no_memory,
        include_compact=not args.no_compact,
    )

    thread_id = args.thread_id or _default_thread_id(args)
    config = {"configurable": {"thread_id": thread_id}}
    return app, config, _initial_state(args), skills_middleware


def _initial_state(args: argparse.Namespace) -> dict[str, Any]:
    state: dict[str, Any] = {"writes_approved": False}
    if args.skill:
        state["pinned_skills"] = args.skill
    if args.domain:
        state["active_domain"] = args.domain
    return state


def _run_turn(
    app: Any,
    state: dict[str, Any],
    config: dict[str, Any],
    skills: SkillsMiddleware,
) -> None:
    state = {**state, "context_window_events": []}
    result: dict[str, Any] = {}
    seen_runtime: dict[str, Any] = {}
    for chunk in app.stream(state, config, stream_mode=["custom", "values"]):
        mode, payload = _unpack_stream_chunk(chunk)
        if mode == "custom":
            _print_runtime_event(payload, skills, seen_runtime)
        elif mode == "values":
            result = payload

    response = _last_ai_response(result.get("messages", []))
    if response:
        console.print()
        console.print(Markdown(response))
    _print_context_window(result)


def _print_runtime_event(
    payload: Any,
    skills: SkillsMiddleware,
    seen_runtime: dict[str, Any],
) -> None:
    if not isinstance(payload, dict):
        console.print(f"[dim]{payload}[/dim]")
        return

    event = payload.get("event")
    if event == "skills_selected":
        if seen_runtime.get("skills_selected"):
            return
        seen_runtime["skills_selected"] = True
        labels = _skill_labels(skills, payload.get("active_skills") or [])
        console.print(
            "[dim]domain prompts: "
            f"[cyan]{', '.join(labels) if labels else 'none'}[/cyan][/dim]"
        )
        return

    if event == "tools_bound":
        return

    if event == "memory_loaded":
        return

    if event == "model_start":
        return

    if event == "model_done":
        return

    if event == "tool_plan":
        return

    if event == "tool_start":
        tool_calls = payload.get("tool_calls") or []
        for tool_call in tool_calls:
            name = tool_call.get("name", "unknown")
            preview = "..." if name == "write_todo_list" else _format_args_preview(tool_call.get("args", {}))
            console.print(f"[dim]→ [magenta]{name}[/magenta]({preview})[/dim]")
        return

    if event == "tool_result":
        return

    if event == "todo_list":
        _print_todo_list(payload.get("todos") or [])
        return

    if event == "approval_required":
        # request_approval() prints the detailed interactive prompt. Emitting
        # this runtime event in parallel can interleave Rich output with input().
        return

    if event == "approval_result":
        approved = payload.get("approved")
        text = "approved" if approved else "rejected"
        console.print(f"[red]approval: {text}[/red]")
        return

    console.print(f"[dim]{payload}[/dim]")


def _last_ai_response(messages: list[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.content and not message.tool_calls:
            return str(message.content)
    return ""


def _print_todo_list(todos: list[Any]) -> None:
    if not todos:
        console.print("[dim]todo: [green](empty)[/green][/dim]")
        return

    console.print("[dim]todo:[/dim]")
    for todo in todos:
        if not isinstance(todo, dict):
            continue
        status = str(todo.get("status", "pending"))
        task = str(todo.get("task", ""))
        marker, style = {
            "pending": ("[ ]", "dim"),
            "in_progress": ("[>]", "cyan"),
            "done": ("[x]", "green"),
            "blocked": ("[!]", "red"),
        }.get(status, ("[ ]", "dim"))
        console.print(
            f"[dim]  {escape(marker)} [{style}]{escape(task)}[/{style}] "
            f"({escape(status)})[/dim]"
        )


def _print_context_window(result: dict[str, Any]) -> None:
    events = result.get("context_window_events")
    if not isinstance(events, list) or not events:
        return

    compacted_events = [
        event for event in events
        if isinstance(event, dict) and event.get("compaction_triggered")
    ]
    console.print()
    if compacted_events:
        event = compacted_events[-1]
        threshold = _positive_int(event.get("threshold"))
        raw_tokens = _non_negative_int(event.get("raw_tokens"))
        model_tokens = _non_negative_int(event.get("model_input_tokens"))
        compacted_messages = _non_negative_int(event.get("compacted_messages"))
        console.print(
            f"[dim]{escape(_format_context_bar('raw context', raw_tokens, threshold))}[/dim]"
        )
        console.print(
            f"[dim]{escape(_format_context_bar('model context', model_tokens, threshold))}[/dim]"
        )
        console.print(
            "[dim]compaction: "
            f"compacted {compacted_messages:,} earlier messages; "
            f"{max(threshold - model_tokens, 0):,} tokens until next compaction[/dim]"
        )
        return

    latest = result.get("context_window")
    if not isinstance(latest, dict):
        latest = events[-1] if isinstance(events[-1], dict) else {}
    threshold = _positive_int(latest.get("threshold"))
    raw_tokens = _non_negative_int(latest.get("raw_tokens"))
    console.print(
        f"[dim]{escape(_format_context_bar('context window', raw_tokens, threshold))}[/dim]"
    )
    console.print(
        "[dim]until compaction: "
        f"{max(threshold - raw_tokens, 0):,} tokens[/dim]"
    )


def _format_context_bar(label: str, tokens: int, threshold: int, width: int = 24) -> str:
    ratio = tokens / threshold if threshold else 0
    filled = min(width, round(ratio * width))
    bar = "█" * filled + "░" * (width - filled)
    return f"{label:<14} [{bar}] {tokens:,} / {threshold:,} tokens {ratio * 100:5.1f}%"


def _positive_int(value: Any, default: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 1)


def _non_negative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _unpack_stream_chunk(chunk: Any) -> tuple[str, Any]:
    if isinstance(chunk, tuple):
        if len(chunk) == 2:
            return str(chunk[0]), chunk[1]
        if len(chunk) == 3:
            return str(chunk[1]), chunk[2]
    return "values", chunk


def _skill_labels(skills: SkillsMiddleware, active_skill_ids: list[str]) -> list[str]:
    labels = []
    for skill_id in active_skill_ids:
        skill = skills.resolve(skill_id)
        labels.append(f"{skill.id} ({skill.name})" if skill else str(skill_id))
    return labels


def _format_args_preview(args: Any) -> str:
    if not isinstance(args, dict):
        return str(args)

    parts = []
    for key, value in args.items():
        preview = str(value).replace("\n", "\\n")
        if len(preview) > 80:
            preview = preview[:77] + "..."
        parts.append(f"{key}={preview!r}")
    return ", ".join(parts)


def _provider_arg(value: str | None) -> Provider | None:
    if value is None:
        return None
    if value not in PROVIDERS:
        raise ValueError(f"Unknown provider: {value}")
    return value  # type: ignore[return-value]


def _provider_label(value: str | None) -> str:
    return value or get_default_provider()


def _default_thread_id(args: argparse.Namespace) -> str:
    provider = args.provider or "auto"
    domain = args.domain or "auto"
    skills = "-".join(args.skill or []) or "auto"
    return f"chat-{provider}-{domain}-{skills}"


if __name__ == "__main__":
    raise SystemExit(main())
