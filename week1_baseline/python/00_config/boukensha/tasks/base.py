from __future__ import annotations

from pathlib import Path
from typing import Any


class Base:
    """Stateless task helpers. All behaviour is classmethods; no instances."""

    @classmethod
    def task_name(cls) -> str:
        raise NotImplementedError(f"{cls} must define .task_name")

    @classmethod
    def provider(cls, settings: dict[str, Any]) -> Any:
        value = cls._fetch(settings, "provider")
        if value:
            return value
        raise ValueError(f"tasks.{cls.task_name()}.provider is required in settings.yml")

    @classmethod
    def model(cls, settings: dict[str, Any]) -> Any:
        value = cls._fetch(settings, "model")
        if value:
            return value
        raise ValueError(f"tasks.{cls.task_name()}.model is required in settings.yml")

    @classmethod
    def prompt_override(cls, settings: dict[str, Any], prompt: str = "system") -> bool:
        node = cls._fetch(settings, "prompt_override")
        if not isinstance(node, dict):
            return False
        return node.get(prompt) is True

    @classmethod
    def prompt(
        cls,
        settings: dict[str, Any],
        name: str = "system",
        user_prompts_dir: str | None = None,
        default_prompts_dir: str | None = None,
    ) -> str | None:
        if cls.prompt_override(settings, name):
            text = cls._read_user_prompt(name, user_prompts_dir=user_prompts_dir)
            if text is not None:
                return text
        return cls._read_default_prompt(name, default_prompts_dir=default_prompts_dir)

    @classmethod
    def system_prompt(
        cls,
        settings: dict[str, Any],
        user_prompts_dir: str | None = None,
        default_prompts_dir: str | None = None,
    ) -> str | None:
        return cls.prompt(
            settings,
            "system",
            user_prompts_dir=user_prompts_dir,
            default_prompts_dir=default_prompts_dir,
        )

    @classmethod
    def _fetch(cls, settings: dict[str, Any], key: str) -> Any:
        return settings.get(key)

    @classmethod
    def _read_user_prompt(
        cls, prompt_name: str, user_prompts_dir: str | None = None
    ) -> str | None:
        if not user_prompts_dir:
            return None
        path = Path(user_prompts_dir) / cls.task_name() / f"{prompt_name}.md"
        return cls._read_file(path)

    @classmethod
    def _read_default_prompt(
        cls, prompt_name: str, default_prompts_dir: str | None = None
    ) -> str | None:
        if not default_prompts_dir:
            return None
        path = Path(default_prompts_dir) / f"{prompt_name}.md"
        return cls._read_file(path)

    @classmethod
    def _read_file(cls, path: Path) -> str | None:
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8").strip()
