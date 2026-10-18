"""Memória em notas Markdown, uma por tópico, ligadas por [[ligações]] (abre como vault do Obsidian).

Cada nota tem um cabeçalho YAML que o Obsidian mostra como propriedades:

    ---
    type: interest
    aliases:
      - "F1"
    mentions: 3
    created: 2026-10-16
    updated: 2026-10-18
    ---
    # Formula 1

    Linked to [[Duarte]]
    Related: [[Max Verstappen]]

    - Follows the championship fight closely. _(2026-10-16)_

Regras principais:
- Um assunto novo vai para a nota que já existe sobre ele (pelo título, pelos aliases ou por
  um nome parecido), em vez de criar uma nota nova.
- Pedidos de rotina ("the news", "the weather") nunca viram tópico.
- Um interesse só visto uma vez fica como candidato em .jarvis/; passa a nota quando volta
  a aparecer noutro dia.
"""
import json
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from difflib import SequenceMatcher
from pathlib import Path

from ..config import settings

INDEX = "Duarte"
LEGACY_INDEX = "Gusta-Gusta"  # nome antigo do índice; é apagado ao reconstruir
STATE_DIR = ".jarvis"  # pastas com ponto não aparecem no Obsidian
KINDS = ("preference", "person", "habit", "fact", "interest")
SECTION = {
    "preference": "Preferences",
    "person": "People",
    "habit": "Habits",
    "fact": "Facts",
    "interest": "Interests",
}
CANDIDATE_TTL_DAYS = 30

# Palavras que não distinguem tópicos ("my family" é o mesmo que "family").
_FILLER = {"the", "a", "an", "my", "his", "of", "about", "and", "s", "gustavo", "gustavos"}

# Pedidos de rotina: o pedido em si não diz nada sobre o Gustavo.
_ROUTINE = (
    "news", "today's news", "daily news", "news today", "latest news", "headlines", "news headlines",
    "news briefing", "morning news", "weather", "weather forecast", "forecast", "time", "date",
    "greeting", "greetings", "small talk", "chit chat", "conversation", "general", "misc",
    "miscellaneous", "question", "questions", "notes", "other",
)

_lock = threading.RLock()


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def _singular(word: str) -> str:
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _tokens(name: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", _ascii(name).lower())
    return [_singular(w) for w in words if w not in _FILLER]


def _key(name: str) -> str:
    return " ".join(_tokens(name))


ROUTINE_KEYS = {_key(t) for t in _ROUTINE}


def is_routine(topic: str) -> bool:
    key = _key(topic)
    return not key or key in ROUTINE_KEYS


def same_topic(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    sa, sb = set(ta), set(tb)
    if sa == sb:
        return True
    small, big = sorted((sa, sb), key=len)
    # "Formula 1" e "Formula 1 season" são o mesmo tópico; "Benfica" e "Benfica stadium tour" não.
    if small <= big and (len(small) >= 2 or len(big) <= 2):
        return True
    return SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio() >= 0.88


def _title(topic: str) -> str:
    topic = re.sub(r"[\\/:*?\"<>|#^\[\]]", " ", topic).strip()
    return re.sub(r"\s+", " ", topic)[:80] or "Notes"


_DATE_SUFFIX = re.compile(r"\s*_\(\d{4}-\d{2}-\d{2}\)_\s*$")


def _fact_text(line: str) -> str:
    return _DATE_SUFFIX.sub("", line).strip()


def _same_fact(a: str, b: str) -> bool:
    na, nb = " ".join(_tokens(_fact_text(a))), " ".join(_tokens(_fact_text(b)))
    return na == nb or SequenceMatcher(None, na, nb).ratio() >= 0.9


# --- Notas ----------------------------------------------------------------------------------


@dataclass
class Note:
    title: str
    kind: str = "fact"
    aliases: list[str] = field(default_factory=list)
    mentions: int = 0
    created: str = ""
    updated: str = ""
    related: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    # Linhas escritas à mão no Obsidian que não são factos; mantêm-se como estão.
    extra: list[str] = field(default_factory=list)

    @property
    def names(self) -> list[str]:
        return [self.title, *self.aliases]

    def matches(self, topic: str) -> bool:
        return any(same_topic(topic, name) for name in self.names)


def _unquote(value: str) -> str:
    value = value.strip()
    if value.startswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value.strip("'\"")


def _parse(path: Path) -> Note:
    lines = path.read_text(encoding="utf-8").splitlines()
    meta: dict[str, object] = {}
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is not None:
            current = None
            for line in lines[1:end]:
                if line.lstrip().startswith("- ") and current:
                    values = meta.setdefault(current, [])
                    if isinstance(values, list):
                        values.append(_unquote(line.lstrip()[2:]))
                elif ":" in line:
                    current, _, value = line.partition(":")
                    current = current.strip()
                    if value.strip():
                        meta[current] = _unquote(value)
            lines = lines[end + 1 :]

    note = Note(title=path.stem)
    kind = str(meta.get("type", "fact"))
    note.kind = kind if kind in KINDS else "fact"
    aliases = meta.get("aliases", [])
    note.aliases = list(aliases) if isinstance(aliases, list) else [str(aliases)]
    try:
        note.mentions = int(str(meta.get("mentions", 0)))
    except ValueError:
        note.mentions = 0
    note.created = str(meta.get("created", ""))
    note.updated = str(meta.get("updated", ""))

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("# "):
            continue
        if re.match(r"^(Linked to|Ligado a) \[\[", stripped):
            continue
        if stripped.startswith("Related:"):
            note.related += re.findall(r"\[\[([^\]]+)\]\]", stripped)
        elif stripped.startswith("- "):
            note.facts.append(stripped[2:].strip())
        else:
            note.extra.append(line)
    if not note.updated:
        note.updated = date.fromtimestamp(path.stat().st_mtime).isoformat()
    note.created = note.created or note.updated
    note.mentions = note.mentions or max(1, len(note.facts))
    return note


def _render(note: Note) -> str:
    out = ["---", f"type: {note.kind}"]
    if note.aliases:
        out.append("aliases:")
        out += [f"  - {json.dumps(a, ensure_ascii=False)}" for a in note.aliases]
    out += [f"mentions: {note.mentions}", f"created: {note.created}", f"updated: {note.updated}", "---"]
    out += [f"# {note.title}", "", f"Linked to [[{INDEX}]]"]
    if note.related:
        out.append("Related: " + ", ".join(f"[[{r}]]" for r in note.related))
    if note.extra:
        out += ["", *note.extra]
    if note.facts:
        out += ["", *(f"- {f}" for f in note.facts)]
    return "\n".join(out) + "\n"


def _dir() -> Path:
    settings.memory_dir.mkdir(parents=True, exist_ok=True)
    return settings.memory_dir


def _write(path: Path, text: str):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def notes() -> list[Note]:
    if not settings.memory_dir.exists():
        return []
    return [_parse(p) for p in sorted(settings.memory_dir.glob("*.md")) if p.stem not in (INDEX, LEGACY_INDEX)]


def find(topic: str, existing: list[Note] | None = None) -> Note | None:
    existing = notes() if existing is None else existing
    exact = _key(topic)
    for note in existing:  # primeiro o nome igual, só depois os parecidos
        if any(_key(n) == exact for n in note.names):
            return note
    return next((n for n in existing if n.matches(topic)), None)


def _rebuild_index(existing: list[Note]):
    out = [f"# {INDEX}", "", "What Duarte knows about Gustavo, one note per topic.", ""]
    for kind in KINDS:
        group = sorted((n for n in existing if n.kind == kind), key=lambda n: (-n.mentions, n.title))
        if group:
            out += [f"## {SECTION[kind]}", *(f"- [[{n.title}]]" for n in group), ""]
    _write(_dir() / f"{INDEX}.md", "\n".join(out))
    (_dir() / f"{LEGACY_INDEX}.md").unlink(missing_ok=True)


def save(topic: str, fact: str, kind: str = "fact", related: list[str] | tuple = ()) -> str:
    """Guarda um facto no tópico certo. Devolve uma frase curta para o Claude."""
    fact = " ".join(fact.split())
    if is_routine(topic):
        return f"Not saved: '{topic}' is a routine request, not something to remember."
    if not fact:
        return "Not saved: empty fact."
    kind = kind if kind in KINDS else "fact"
    today = date.today().isoformat()
    with _lock:
        existing = notes()
        note = find(topic, existing)
        created = note is None
        if note is None:
            note = Note(title=_title(topic), kind=kind, created=today)
            existing.append(note)
        elif _key(topic) not in {_key(n) for n in note.names} and len(note.aliases) < 10:
            note.aliases.append(_title(topic))
        if kind == "interest" and note.kind == "fact":
            note.kind = "interest"

        duplicate = any(_same_fact(fact, f) for f in note.facts)
        if not duplicate:
            note.facts.append(f"{fact} _({today})_")
        note.mentions += 1
        note.updated = today
        for name in related:
            other = find(name, existing)
            link = other.title if other else _title(name)
            if link != note.title and link not in note.related:
                note.related.append(link)

        _write(_dir() / f"{note.title}.md", _render(note))
        _rebuild_index(existing)
    if created:
        return f"Saved under a new topic, {note.title}."
    if duplicate:
        return f"Already known, under {note.title}."
    return f"Saved under the existing topic {note.title}."


# --- Candidatos a interesse -----------------------------------------------------------------


def _candidates_path() -> Path:
    path = _dir() / STATE_DIR
    path.mkdir(exist_ok=True)
    return path / "candidates.json"


def _load_candidates() -> dict:
    path = _candidates_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def note_candidate(topic: str, detail: str) -> str:
    """Um assunto perguntado uma vez, sem continuação. Vira interesse se voltar noutro dia."""
    if is_routine(topic):
        return "ignored"
    today = date.today()
    with _lock:
        note = find(topic)
        if note is not None:
            # Já é um tópico: voltar a ele conta como mais uma menção.
            save(note.title, detail, kind=note.kind)
            return "existing"
        cutoff = (today - timedelta(days=CANDIDATE_TTL_DAYS)).isoformat()
        cands = {k: v for k, v in _load_candidates().items() if max(v["dates"]) >= cutoff}
        key = next((k for k, v in cands.items() if same_topic(topic, v["title"])), _key(topic))
        entry = cands.setdefault(key, {"title": _title(topic), "dates": [], "details": []})
        if today.isoformat() not in entry["dates"]:
            entry["dates"].append(today.isoformat())
        entry["details"] = (entry["details"] + [" ".join(detail.split())])[-3:]
        promote = len(entry["dates"]) >= 2
        if promote:
            del cands[key]
        _write(_candidates_path(), json.dumps(cands, ensure_ascii=False, indent=2))
        if promote:
            for d in entry["details"]:
                save(entry["title"], d, kind="interest")
            return "promoted"
    return "pending"


# --- Leitura --------------------------------------------------------------------------------


def recall(topic: str) -> str:
    """Tudo o que está guardado sobre um tópico, mais um resumo dos tópicos ligados."""
    existing = notes()
    note = find(topic, existing)
    if note is None:
        close = [n.title for n in existing if SequenceMatcher(None, _key(topic), _key(n.title)).ratio() > 0.5]
        hint = f" Closest topics: {', '.join(close[:5])}." if close else ""
        return f"Nothing saved about {topic}.{hint}"
    lines = [f"{note.title} ({note.kind}, mentioned {note.mentions} times, last on {note.updated}):"]
    lines += [f"- {_fact_text(f)}" for f in note.facts]
    lines += [line.strip() for line in note.extra if line.strip()]
    for name in note.related:
        other = find(name, existing)
        if other and other.facts:
            lines.append(f"Related, {other.title}: " + "; ".join(_fact_text(f) for f in other.facts[-3:]))
    return "\n".join(lines)


def load_context(max_chars: int = 5000) -> str:
    """Resumo para o prompt: perfil, interesses e a lista de tópicos que já existem."""
    existing = sorted(notes(), key=lambda n: (n.mentions, n.updated), reverse=True)
    if not existing:
        return ""
    profile = [n for n in existing if n.kind != "interest"]
    interests = [n for n in existing if n.kind == "interest"]

    out: list[str] = []
    used = 0

    def add(line: str) -> bool:
        nonlocal used
        if used + len(line) > max_chars:
            return False
        out.append(line)
        used += len(line) + 1
        return True

    if profile and add("About him:"):
        for n in profile:
            if not add(f"- {n.title}: " + "; ".join(_fact_text(f) for f in n.facts[-5:])):
                break
    if interests and add("Topics he follows, most mentioned first:"):
        for n in interests:
            last = _fact_text(n.facts[-1]) if n.facts else ""
            if not add(f"- {n.title} (mentioned {n.mentions} times, last on {n.updated}): {last}"):
                break
    add("Existing memory topics: " + ", ".join(n.title for n in existing))
    return "\n".join(out)
