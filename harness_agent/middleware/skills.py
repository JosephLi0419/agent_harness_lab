"""Skills middleware for runtime skill prompt injection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage

from .base import AgentMiddleware, AgentState, append_to_system

DEFAULT_SKILL_ID = "general_research"
ROUTER_CONFIDENCE_THRESHOLD = 0.5
SKILL_FRONTMATTER_DELIMITER = "---"
SKILL_FRONTMATTER_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SKILL_ROUTER_SYSTEM_PROMPT = """You are a skill router for an agent runtime.

Choose the single best skill for the user's latest message.

Rules:
- Use only the provided skill routing descriptions.
- Return the broad fallback skill when no specialized skill clearly fits.
- Return only valid JSON with these keys: name, confidence, reason.
- name must exactly match one of the provided skill names.
- confidence must be a number from 0 to 1.
"""


@dataclass(frozen=True)
class Skill:
    """A prompt-backed capability that can be activated at runtime."""

    id: str
    name: str
    routing_name: str
    version: str
    prompt_path: Path
    routing_description: str
    trigger_keywords: tuple[str, ...] = ()

    @property
    def instructions(self) -> str:
        """Load the complete prompt only after this skill has been selected."""
        return _read_text(self.prompt_path)


class SkillsMiddleware(AgentMiddleware):
    """Select active skills before each model call and inject their instructions.

    Skills live in `harness_agent/skills/<skill_id>/` with:
    - `SKILL.md` for front matter metadata plus prompt instructions
    """

    name = "skills"

    def __init__(
        self,
        *,
        prompt_dir: Path | None = None,
        skills_dir: Path | None = None,
        fallback_skill_id: str | None = DEFAULT_SKILL_ID,
        router_llm: Any | None = None,
        router_confidence_threshold: float = ROUTER_CONFIDENCE_THRESHOLD,
    ):
        self.prompt_dir = prompt_dir or Path(__file__).resolve().parents[1] / "prompts"
        self.skills_dir = skills_dir or Path(__file__).resolve().parents[1] / "skills"
        self.fallback_skill_id = normalize_skill_id(fallback_skill_id) if fallback_skill_id else None
        self.router_llm = router_llm
        self.router_confidence_threshold = router_confidence_threshold
        self._base_prompt = _read_text(self.prompt_dir / "SOUL.md")
        self._skills = self._load_skills()
        self._lookup = self._build_lookup()

    @property
    def base_prompt(self) -> str:
        return self._base_prompt

    def list_skills(self) -> list[Skill]:
        """Return all known skills sorted by id."""
        return [self._skills[key] for key in sorted(self._skills)]

    def resolve(self, skill_id_or_alias: str | None) -> Skill | None:
        """Resolve a skill by id, filename-like id, or alias."""
        if not skill_id_or_alias:
            return None
        return self._lookup.get(normalize_skill_id(skill_id_or_alias))

    def before_model(
        self,
        messages: Sequence[AnyMessage],
        state: AgentState,
    ) -> Sequence[AnyMessage]:
        active_skills = self.select_skill_ids(
            {**state, "messages": list(messages)},
            fallback_skill_id=self.fallback_skill_id,
        )
        state["active_skills"] = active_skills
        state["last_skill_route_user_text"] = _latest_human_text(list(messages)).strip()
        return messages

    def inject_system(self, system: str, state: AgentState) -> str:
        active_skills = self._resolve_many(_coerce_skill_list(state.get("active_skills")))
        if not active_skills:
            active_skills = self.select_skill_ids(
                state,
                fallback_skill_id=self.fallback_skill_id,
            )
            state["active_skills"] = active_skills

        skill_prompt = self.render_skill_instructions(active_skills)
        if not skill_prompt:
            return system

        return append_to_system(
            system,
            "<active_skills>\n"
            f"{', '.join(active_skills)}\n"
            "</active_skills>\n\n"
            f"{skill_prompt}",
        )

    def select_skill_ids(
        self,
        state: dict[str, Any],
        *,
        fallback_skill_id: str | None = None,
    ) -> list[str]:
        """Pick skill ids using slash commands, pinned state, routing, then fallback."""
        command_skill = self._skill_from_latest_command(state.get("messages", []))
        if command_skill:
            state["pinned_skills"] = [command_skill.id]
            return [command_skill.id]

        pinned = self._resolve_many(_coerce_skill_list(state.get("pinned_skills")))
        if pinned:
            return pinned

        domain = self._resolve_many(_coerce_skill_list(state.get("active_domain")))
        if domain:
            return domain

        legacy_explicit = self._resolve_many(_coerce_skill_list(state.get("active_skills")))
        if legacy_explicit and not state.get("messages"):
            return legacy_explicit

        resolved = self._resolve_many(_coerce_skill_list(state.get("skill_ids")))
        if resolved:
            return resolved

        latest_user_text = _latest_human_text(state.get("messages", [])).strip()
        cached_text = str(state.get("last_skill_route_user_text") or "").strip()
        cached_skills = self._resolve_many(_coerce_skill_list(state.get("active_skills")))
        if latest_user_text and cached_text == latest_user_text and cached_skills:
            return cached_skills

        routed_skill = self._route_latest_message(state.get("messages", []))
        if routed_skill:
            return [routed_skill.id]

        fallback = self.resolve(fallback_skill_id) if fallback_skill_id else None
        if fallback:
            return [fallback.id]

        default = self.resolve(DEFAULT_SKILL_ID)
        return [default.id] if default else []

    def render_system_prompt(self, skill_ids: list[str]) -> str:
        """Render SOUL plus the selected skill instructions."""
        parts = [self.base_prompt, self.render_skill_instructions(skill_ids)]
        return "\n\n---\n\n".join(part for part in parts if part)

    def render_skill_instructions(self, skill_ids: list[str]) -> str:
        """Render only the selected skill instructions."""
        parts = []
        for skill_id in skill_ids:
            skill = self.resolve(skill_id)
            if skill:
                parts.append(skill.instructions)
        return "\n\n---\n\n".join(part for part in parts if part)

    def _load_skills(self) -> dict[str, Skill]:
        skills: dict[str, Skill] = {}
        for skill_dir in sorted(self.skills_dir.iterdir() if self.skills_dir.exists() else []):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            frontmatter = _read_skill_frontmatter(skill_file)
            skill_id = normalize_skill_id(skill_dir.name)
            routing_name = str(frontmatter.get("name") or skill_id).strip()
            trigger_keywords = _read_string_tuple(frontmatter.get("trigger_keywords"))
            skills[skill_id] = Skill(
                id=skill_id,
                name=routing_name,
                routing_name=routing_name,
                version=str(frontmatter.get("version") or "").strip(),
                prompt_path=skill_file,
                routing_description=str(frontmatter.get("description") or "").strip(),
                trigger_keywords=trigger_keywords,
            )
        return skills

    def _build_lookup(self) -> dict[str, Skill]:
        lookup: dict[str, Skill] = {}
        for skill in self._skills.values():
            keys = {skill.id, skill.routing_name}
            for key in keys:
                lookup[normalize_skill_id(key)] = skill
        return lookup

    def _resolve_many(self, raw_skill_ids: list[str]) -> list[str]:
        resolved: list[str] = []
        for raw_skill_id in raw_skill_ids:
            skill = self.resolve(raw_skill_id)
            if skill and skill.id not in resolved:
                resolved.append(skill.id)
        return resolved

    def _skill_from_latest_command(self, messages: list[AnyMessage]) -> Skill | None:
        text = _latest_human_text(messages).strip()
        lowered = text.lower()
        for prefix in ("/skill ", "/domain "):
            if lowered.startswith(prefix):
                requested = text[len(prefix):].strip()
                return self.resolve(requested)
        return None

    def _route_latest_message(self, messages: list[AnyMessage]) -> Skill | None:
        text = _latest_human_text(messages).strip()
        if not text:
            return None
        if self.router_llm is None:
            return None

        prompt = _render_router_prompt(
            user_text=text,
            skills=self.list_skills(),
        )
        try:
            response = self.router_llm.invoke([
                SystemMessage(content=SKILL_ROUTER_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
        except Exception:
            return None

        decision = _parse_router_decision(_message_content(response))
        if not decision:
            return None

        selected_name = str(
            decision.get("name")
            or decision.get("skill_name")
            or decision.get("skill_id")
            or decision.get("skill")
            or ""
        )
        skill = self.resolve(selected_name)
        if not skill:
            return None

        confidence = _coerce_confidence(decision.get("confidence"))
        if confidence < self.router_confidence_threshold:
            return None

        return skill


def normalize_skill_id(value: str) -> str:
    """Normalize folder names, front matter names, and state values to comparable ids."""
    return value.strip().replace("-", "_").replace(" ", "_").lower()


def _coerce_skill_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value]
    return [str(value)]


def _latest_human_text(messages: list[AnyMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return message.content if isinstance(message.content, str) else str(message.content)
    return ""


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _read_skill_frontmatter(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != SKILL_FRONTMATTER_DELIMITER:
        return {}

    frontmatter_lines: list[str] = []
    for line in lines[1:]:
        if line.strip() == SKILL_FRONTMATTER_DELIMITER:
            return _parse_skill_frontmatter(frontmatter_lines)
        frontmatter_lines.append(line)
    return {}


def _parse_skill_frontmatter(lines: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        if ":" not in line:
            i += 1
            continue

        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = _strip_yaml_comment(raw_value).strip()

        if key == "description" and value == "|":
            i += 1
            description_lines: list[str] = []
            while i < len(lines):
                candidate = lines[i]
                if candidate.strip() and not candidate.startswith((" ", "\t")):
                    break
                description_lines.append(candidate[2:] if candidate.startswith("  ") else candidate.strip())
                i += 1
            parsed[key] = "\n".join(description_lines).strip()
            continue

        if key == "trigger_keywords":
            keywords: list[str] = []
            if value:
                keywords.extend(_parse_inline_list(value))
            i += 1
            while i < len(lines):
                candidate = lines[i]
                stripped_candidate = candidate.strip()
                if not stripped_candidate:
                    i += 1
                    continue
                if not candidate.startswith((" ", "\t")):
                    break
                if stripped_candidate.startswith("- "):
                    keywords.append(_strip_yaml_comment(stripped_candidate[2:]).strip().strip("\"'"))
                i += 1
            parsed[key] = tuple(keyword for keyword in keywords if keyword)
            continue

        if key == "name":
            value = value.strip("\"'")
            if SKILL_FRONTMATTER_NAME_RE.match(value):
                parsed[key] = value
        elif key == "version":
            parsed[key] = value.strip("\"'")
        else:
            parsed[key] = value.strip("\"'")
        i += 1
    return parsed


def _strip_yaml_comment(value: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(value):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return value[:index]
    return value


def _parse_inline_list(value: str) -> list[str]:
    stripped = value.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        return [stripped.strip("\"'")]
    inner = stripped[1:-1].strip()
    if not inner:
        return []
    return [item.strip().strip("\"'") for item in inner.split(",")]


def _read_string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return (str(value),)


def _render_router_prompt(
    *,
    user_text: str,
    skills: list[Skill],
) -> str:
    options = []
    for skill in skills:
        trigger_keywords = ", ".join(skill.trigger_keywords) if skill.trigger_keywords else "-"
        description = skill.routing_description or "-"
        options.append(
            f"Name: {skill.routing_name}\n"
            f"Version: {skill.version or '-'}\n"
            f"Trigger keywords: {trigger_keywords}\n"
            f"Description:\n{description}"
        )

    options_text = "\n\n".join(options)
    return (
        "Available skills:\n\n"
        f"{options_text}\n\n"
        "Latest user message:\n"
        f"{user_text}\n\n"
        "Choose the best skill by front matter name and return JSON only."
    )


def _message_content(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text is not None:
                    parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _parse_router_decision(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if not cleaned:
        return None

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    return parsed if isinstance(parsed, dict) else None


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(confidence, 1.0))
