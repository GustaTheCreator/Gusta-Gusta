"""Memória em notas Markdown ligadas por [[ligações]], para abrir como vault do Obsidian."""
import re
from datetime import date
from pathlib import Path

from ..config import settings

INDEX = "Jarvis"


def _slug(topic: str) -> str:
    topic = re.sub(r"[\\/:*?\"<>|#^\[\]]", " ", topic).strip()
    return re.sub(r"\s+", " ", topic)[:80] or "Notas"


def _dir() -> Path:
    settings.memory_dir.mkdir(parents=True, exist_ok=True)
    return settings.memory_dir


def save(topic: str, fact: str) -> str:
    title = _slug(topic)
    path = _dir() / f"{title}.md"
    if not path.exists():
        path.write_text(f"# {title}\n\nLigado a [[{INDEX}]]\n\n", encoding="utf-8")
        index = _dir() / f"{INDEX}.md"
        if not index.exists():
            index.write_text(f"# {INDEX}\n\nO que sei sobre o Gustavo.\n\n", encoding="utf-8")
        with index.open("a", encoding="utf-8") as f:
            f.write(f"- [[{title}]]\n")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"- {fact.strip()} _({date.today().isoformat()})_\n")
    return f"Saved under {title}."


def load_context(max_chars: int = 6000) -> str:
    """Notas mais recentes primeiro, cortadas para caberem no prompt."""
    if not settings.memory_dir.exists():
        return ""
    notes = sorted(
        (p for p in settings.memory_dir.glob("*.md") if p.stem != INDEX),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out, used = [], 0
    for note in notes:
        text = note.read_text(encoding="utf-8").strip()
        if used + len(text) > max_chars:
            break
        out.append(text)
        used += len(text)
    return "\n\n".join(out)
