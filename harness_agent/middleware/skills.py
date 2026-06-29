"""Skills middleware for runtime skill prompt injection."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import Any

from langchain_core.messages import AnyMessage, HumanMessage

from .base import AgentMiddleware, AgentState, append_to_system

DEFAULT_SKILL_ID = "general_research"


@dataclass(frozen=True)
class Skill:
    """A prompt-backed capability that can be activated at runtime."""

    id: str
    name: str
    instructions: str
    aliases: tuple[str, ...] = ()
    triggers: tuple[str, ...] = ()


class SkillsMiddleware(AgentMiddleware):
    """Select active skills before each model call and inject their instructions.

    Skills live in `harness_agent/skills/<skill_id>/` with:
    - `SKILL.md` for prompt instructions
    - `manifest.toml` for id, name, aliases, and routing triggers
    """

    name = "skills"

    def __init__(
        self,
        *,
        prompt_dir: Path | None = None,
        skills_dir: Path | None = None,
        fallback_skill_id: str | None = DEFAULT_SKILL_ID,
    ):
        self.prompt_dir = prompt_dir or Path(__file__).resolve().parents[1] / "prompts"
        self.skills_dir = skills_dir or Path(__file__).resolve().parents[1] / "skills"
        self.fallback_skill_id = normalize_skill_id(fallback_skill_id) if fallback_skill_id else None
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
        return messages

    def inject_system(self, system: str, state: AgentState) -> str:
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

        routed_skill = self._route_latest_message(state.get("messages", []))
        if routed_skill:
            return [routed_skill.id]

        domain = self._resolve_many(_coerce_skill_list(state.get("active_domain")))
        if domain:
            return domain

        legacy_explicit = self._resolve_many(_coerce_skill_list(state.get("active_skills")))
        if legacy_explicit and not state.get("messages"):
            return legacy_explicit

        resolved = self._resolve_many(_coerce_skill_list(state.get("skill_ids")))
        if resolved:
            return resolved

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
            manifest = _read_manifest(skill_dir / "manifest.toml")
            skill_id = normalize_skill_id(str(manifest.get("id") or skill_dir.name))
            skills[skill_id] = Skill(
                id=skill_id,
                name=str(manifest.get("name") or skill_id),
                instructions=_read_text(skill_file),
                aliases=_read_string_tuple(manifest.get("aliases")),
                triggers=_read_string_tuple(manifest.get("triggers")),
            )
        return skills

    def _build_lookup(self) -> dict[str, Skill]:
        lookup: dict[str, Skill] = {}
        for skill in self._skills.values():
            keys = {skill.id, skill.name, *skill.aliases}
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
        text = _latest_human_text(messages).lower()
        if not text:
            return None

        best_skill: Skill | None = None
        best_score = 0
        for skill in self._skills.values():
            score = sum(1 for trigger in skill.triggers if trigger.lower() in text)
            if score > best_score:
                best_skill = skill
                best_score = score
        return best_skill if best_score else None


def normalize_skill_id(value: str) -> str:
    """Normalize filenames, aliases, and state values to comparable ids."""
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


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _read_string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return (str(value),)
