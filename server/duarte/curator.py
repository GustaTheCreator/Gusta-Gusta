"""Revisão da conversa no fim de cada ligação: o que vale a pena guardar e em que tópico.

Corre depois de desligares, fora do caminho da voz, por isso não atrasa respostas.
"""
from typing import Literal

from claude_agent_sdk import ClaudeSDKError, ResultMessage, query
from loguru import logger
from pydantic import BaseModel, Field

from .brain import base_options
from .config import settings
from .tools import memory

GREETING_MARK = "(It is "  # a instrução da saudação, que não é o Gustavo a falar

INSTRUCTIONS = """You maintain the long-term memory of Duarte, Gustavo's voice assistant. Read the conversation and decide what is worth remembering for future days. Most conversations contain nothing worth keeping; returning empty lists is normal.

Save (in "updates"):
- Preferences, habits, plans and facts about his life or the people in it that he states.
- A subject he showed real interest in: he asked a follow-up, asked for more detail, or kept talking about the same specific subject. Example: he asks for today's news and then asks more about one story. Save that story's subject as an interest, with one sentence on what it is about and what he wanted to know.

Do not save:
- The routine request itself (asking for the news, the weather, the time, greetings, thanks).
- Headlines or answers he heard without reacting to them.
- What Duarte said, unless Gustavo confirmed it as true about himself.
- Anything already in the existing memory below.

Put a specific subject he asked about only once, without any follow-up, in "candidates" instead. It becomes an interest if he brings it up again on another day.

Topics:
- Reuse an existing topic title exactly when the subject matches one, even loosely. Only create a new topic for a genuinely new subject.
- A topic is a short English noun phrase, general enough to collect future facts: "Formula 1", not "Verstappen's win on Sunday"; "Family", not "Mum's birthday".
- Facts are one sentence each, in the third person ("He prefers..."), in English. The conversation itself is in Portuguese: translate, and keep the memory notes in English."""


class Update(BaseModel):
    topic: str
    kind: Literal["preference", "person", "habit", "fact", "interest"]
    facts: list[str]
    related: list[str] = Field(default_factory=list, description="Other topic titles this one links to")


class Candidate(BaseModel):
    topic: str
    detail: str = Field(description="One sentence on what he asked")


class Review(BaseModel):
    updates: list[Update]
    candidates: list[Candidate]


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def transcript(messages: list) -> str:
    """Só o que o Gustavo e o Duarte disseram, sem chamadas a ferramentas."""
    lines = []
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") not in ("user", "assistant"):
            continue
        text = " ".join(_text(msg.get("content")).split())
        if not text or text.startswith(GREETING_MARK):
            continue
        lines.append(f"{'Gustavo' if msg['role'] == 'user' else 'Duarte'}: {text}")
    return "\n".join(lines)


def apply(review: Review) -> int:
    changed = 0
    for update in review.updates:
        for fact in update.facts:
            result = memory.save(update.topic, fact, kind=update.kind, related=update.related)
            changed += result.startswith("Saved")
    for cand in review.candidates:
        changed += memory.note_candidate(cand.topic, cand.detail) == "promoted"
    return changed


async def review(messages: list):
    convo = transcript(messages)
    if "Gustavo:" not in convo:
        return
    existing = memory.load_context() or "(empty)"
    options = base_options(
        model=settings.memory_model,
        system_prompt=INSTRUCTIONS,
        output_format={"type": "json_schema", "schema": Review.model_json_schema()},
    )
    prompt = (
        f"<existing_memory>\n{existing}\n</existing_memory>\n\n"
        f"<conversation>\n{convo}\n</conversation>"
    )
    parsed = None
    try:
        async for msg in query(prompt=prompt, options=options):
            if isinstance(msg, ResultMessage) and msg.structured_output is not None:
                parsed = Review.model_validate(msg.structured_output)
    except (ClaudeSDKError, ValueError) as exc:
        logger.warning(f"Memory review failed: {exc.__class__.__name__}")
        return
    if parsed is None:
        logger.warning("Memory review returned nothing")
        return
    changed = apply(parsed)
    logger.info(f"Memory review: {changed} change(s)")
