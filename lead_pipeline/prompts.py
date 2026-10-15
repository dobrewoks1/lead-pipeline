"""Промпты хранятся файлами ``prompts/<имя>.v<N>.md`` с коротким заголовком-метаданными.

Формат файла::

    ---
    name: lead_analysis
    version: v2
    model: claude-haiku-5-5
    changelog: что изменилось по сравнению с прошлой версией
    ---
    Текст системного промпта...

Выбор версии: явно (``PROMPT_VERSION=v1``) или последняя по номеру.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import PROMPTS_DIR

_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_FILE_RE = re.compile(r"^(?P<name>[a-z_]+)\.v(?P<num>\d+)\.md$")


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    text: str
    meta: dict[str, str]
    path: Path

    @property
    def number(self) -> int:
        return int(self.version.lstrip("v"))


def parse_prompt_file(path: Path) -> Prompt:
    raw = path.read_text(encoding="utf-8")
    match = _FRONT_RE.match(raw)
    meta: dict[str, str] = {}
    body = raw
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()
        body = raw[match.end():]
    file_match = _FILE_RE.match(path.name)
    if not file_match:
        raise ValueError(f"Имя файла промпта должно быть вида name.vN.md: {path.name}")
    return Prompt(
        name=meta.get("name", file_match.group("name")),
        version=meta.get("version", f"v{file_match.group('num')}"),
        text=body.strip(),
        meta=meta,
        path=path,
    )


def list_prompts(name: str = "lead_analysis", directory: Path = PROMPTS_DIR) -> list[Prompt]:
    """Все версии промпта по возрастанию номера."""
    prompts = [parse_prompt_file(p) for p in Path(directory).glob(f"{name}.v*.md")]
    return sorted(prompts, key=lambda p: p.number)


def load_prompt(name: str = "lead_analysis", version: str | None = None, directory: Path = PROMPTS_DIR) -> Prompt:
    """Загрузить указанную версию промпта или последнюю."""
    prompts = list_prompts(name, directory)
    if not prompts:
        raise FileNotFoundError(f"Промпты {name}.v*.md не найдены в {directory}")
    if version is None:
        return prompts[-1]
    for prompt in prompts:
        if prompt.version == version:
            return prompt
    raise FileNotFoundError(f"Промпт {name} версии {version} не найден (есть: {[p.version for p in prompts]})")
