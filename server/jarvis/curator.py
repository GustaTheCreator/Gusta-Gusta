"""Revisão da conversa no fim de cada ligação: o que vale a pena guardar e em que tópico.

Corre depois de desligares, fora do caminho da voz, por isso não atrasa respostas.
"""
from functools import lru_cache
from typing import Literal

import anthropic
from loguru import logger
from pydantic import BaseModel, Field

from .config import settings
from .tools import memory

GREETING_MARK = "(It is "  # a instrução da saudação, que não é o Gustavo a falar

INSTRUCTIONS = """You maintain the long-term memory of Gusta-Gusta, Gustavo's voice assistant. Read the conversation and decide what is worth remembering for future days. Most conversations contain nothing worth keeping; returning empty lists is normal.

Save (in "updates"):
- Preferences, habits, plans and facts about his life or the people in it that he states.
- A subject he showed real interest in: he asked a follow-up, asked for more detail, or kept talking about the same specific subject. Example: he asks for today's news and then asks more about one story. Save that story's subject as an interest, with one sentence on what it is about and what he wanted to know.

Do not save:
- The routine request itself (asking for the news, the weather, the time, greetings, thanks).
- Headlines or answers he heard without reacting to them.
- What Gusta-Gusta said, unless Gustavo confirmed it as true about himself.
- Anything already in the existing memory below.

Put a specific subject he asked about only once, without any follow-up, in "candidates" instead. It becomes an interest if he brings it up again on another day.

Topics:
- Reuse an existing topic title exactly when the subject matches one, even loosely. Only create a new topic for a genuinely new subject.
- A topic is a short English noun phrase, general enough to collect future facts: "Formula 1", not "Verstappen's win on Sunday"; "Family", not "Mum's birthday".
- Facts are one sentence each, in the third person ("He prefers..."), in English."""


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


@lru_cache(maxsize=1)
def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or None)


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def transcript(messages: list) -> str:
    """Só o que o Gustavo e o Gusta-Gusta disseram, sem chamadas a ferramentas."""
    lines = []
    for msg in messages:
        if not isinstance(msg, dict) or msg.get("role") not in ("user", "assistant"):
            continue
        text = " ".join(_text(msg.get("content")).split())
        if not text or text.startswith(GREETING_MARK):
            continue
        lines.append(f"{'Gustavo' if msg['role'] == 'user' else 'Gusta-Gusta'}: {text}")
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
    try:
        response = await _client().messages.parse(
            model=settings.memory_model,
            max_tokens=4000,
            system=INSTRUCTIONS,
            messages=[
                {
                    "role": "user",
                    "content": f"<existing_memory>\n{existing}\n</existing_memory>\n\n"
                    f"<conversation>\n{convo}\n</conversation>",
                }
            ],
            output_format=Review,
        )
    except anthropic.APIError as exc:
        logger.warning(f"Memory review failed: {exc.__class__.__name__}")
        return
    if response.stop_reason == "refusal" or response.parsed_output is None:
        logger.warning("Memory review returned nothing")
        return
    changed = apply(response.parsed_output)
    logger.info(f"Memory review: {changed} change(s)")
