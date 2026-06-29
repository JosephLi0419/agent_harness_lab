"""Memory middleware for loading persistent notes into the system prompt."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from langchain_core.messages import AnyMessage

from .base import AgentMiddleware, AgentState, append_to_system

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = PROJECT_ROOT / "memory"
GLOBAL_MEMORY_FILE = MEMORY_DIR / "AGENTS.md"
DOMAIN_MEMORY_DIR = MEMORY_DIR / "domains"
SKILL_MEMORY_FILES = {
    "general_research": "general_research.md",
    "job_search": "job_search.md",
    "stock_research": "stock_research.md",
    "weather_reports": "weather_reports.md",
}
SKILL_MEMORY_HEADERS = {
    "general_research": "# General Research Memory\n\n## Preferences\n\n## Research Log\n",
    "job_search": "# Job Search Memory\n\n## Preferences\n\n## Research Log\n",
    "stock_research": "# Stock Research Memory\n\n## Preferences\n\n## Research Log\n",
    "weather_reports": "# Weather Reports Memory\n\n## Preferences\n\n## Research Log\n",
}

_MEMORY_GUIDELINES = """<memory_middleware>
Memory files may contain durable user preferences and prior research context.

Memory file routing:
- Global memory, for cross-domain assistant behavior and user-wide preferences only: {global_memory_path}
- Active skill/domain memory, for domain preferences, reusable domain knowledge, and completed research findings:
{active_memory_paths}

When to update memory:
- The user states a stable preference.
- The user corrects the agent's behavior or output style.
- A recurring research pattern should persist across sessions.

Do not store credentials, secrets, or one-time temporary details.

If a useful durable note is discovered:
- Prefer the first matching active skill/domain memory file for domain-specific content.
- Use global memory only for cross-domain preferences such as name, language, tone, or general report style.
- Do not put stock, job, weather, or research-domain knowledge in global memory when an active skill memory file is listed.

Use dated entries when summarizing completed research. Call `get_datetime` first
when a memory entry needs the current date.
</memory_middleware>"""


class MemoryMiddleware(AgentMiddleware):
    """Load global and domain-specific memory once, then inject it per call."""

    name = "memory"

    def __init__(self, domain: str | None = None):
        self.domain = domain

    def before_agent(self, state: AgentState) -> AgentState | None:
        updates: AgentState = {}

        if not state.get("global_memory_loaded"):
            updates["global_memory_loaded"] = True
            updates["global_memory"] = _read_file(GLOBAL_MEMORY_FILE)

        return updates or None

    def before_model(
        self,
        messages: Sequence[AnyMessage],
        state: AgentState,
    ) -> Sequence[AnyMessage]:
        """Load memory files for the active skill selected earlier in the stack."""
        loaded: dict[str, str] = {}
        active_paths: list[str] = []
        active_keys = _active_memory_keys(state, self.domain)

        for key in active_keys:
            for path in _memory_paths_for_key(key):
                active_paths.append(str(path))
                content = _read_file(path)
                if content:
                    loaded[str(path)] = content

        state["active_memory_paths"] = _dedupe(active_paths)
        state["domain_memory_files"] = loaded
        return messages

    def inject_system(self, system: str, state: AgentState) -> str:
        global_memory = state.get("global_memory", "")
        domain_memory_files = state.get("domain_memory_files", {})

        parts: list[str] = []
        memory_content = []

        if global_memory:
            memory_content.append(f"{GLOBAL_MEMORY_FILE}\n{global_memory}")
        if isinstance(domain_memory_files, dict):
            for file_path, content in sorted(domain_memory_files.items()):
                if content:
                    memory_content.append(f"{file_path}\n{content}")

        if memory_content:
            parts.append("<agent_memory>\n" + "\n\n".join(memory_content) + "\n</agent_memory>")

        parts.append(_MEMORY_GUIDELINES.format(
            global_memory_path=GLOBAL_MEMORY_FILE,
            active_memory_paths=_format_memory_paths(state.get("active_memory_paths", [])),
        ))

        return append_to_system(system, "\n\n".join(parts))


def ensure_memory_files(domain: str | None = None) -> None:
    """Create memory directories and starter files if they do not exist."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    DOMAIN_MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    if not GLOBAL_MEMORY_FILE.exists():
        GLOBAL_MEMORY_FILE.write_text(
            "# Agent Memory\n\n## User Preferences\n\n## Notes\n",
            encoding="utf-8",
        )

    for key, filename in SKILL_MEMORY_FILES.items():
        path = DOMAIN_MEMORY_DIR / filename
        if not path.exists():
            path.write_text(
                SKILL_MEMORY_HEADERS.get(
                    key,
                    f"# {key.replace('_', ' ').title()} Memory\n\n## Preferences\n\n## Research Log\n",
                ),
                encoding="utf-8",
            )

    if domain:
        domain_file = DOMAIN_MEMORY_DIR / f"{domain}.md"
        if not domain_file.exists():
            domain_file.write_text(
                f"# {domain}\n\n## Preferences\n\n## Research Log\n",
                encoding="utf-8",
            )


def _active_memory_keys(state: AgentState, configured_domain: str | None) -> list[str]:
    keys: list[str] = []
    active_skills = state.get("active_skills", [])
    if isinstance(active_skills, str):
        values = [active_skills]
    elif isinstance(active_skills, list | tuple | set):
        values = [str(value) for value in active_skills]
    else:
        values = []

    for value in [*values, state.get("active_domain"), configured_domain]:
        if not value:
            continue
        key = str(value)
        if key not in keys:
            keys.append(key)
    return keys


def _memory_paths_for_key(key: str) -> list[Path]:
    paths = []
    skill_memory_file = SKILL_MEMORY_FILES.get(key)
    if skill_memory_file:
        paths.append(DOMAIN_MEMORY_DIR / skill_memory_file)
    else:
        paths.append(DOMAIN_MEMORY_DIR / f"{key}.md")
    return paths


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _format_memory_paths(paths: object) -> str:
    if isinstance(paths, list) and paths:
        return "\n".join(f"  - {path}" for path in paths)
    return "  - (none)"


def _read_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
