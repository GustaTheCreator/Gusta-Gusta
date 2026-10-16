"""Pesquisa web: um pedido à parte ao Claude com a ferramenta web_search do servidor."""
from functools import lru_cache

import anthropic

from ..config import settings

MAX_CONTINUATIONS = 3

INSTRUCTIONS = (
    "Search the web and answer the question below with the key facts only, in at most "
    "five short sentences, in English. No URLs, no lists."
)


@lru_cache(maxsize=1)
def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or None)


async def search(query: str) -> str:
    messages = [{"role": "user", "content": f"{INSTRUCTIONS}\n\nQuestion: {query}"}]
    response = None
    for _ in range(MAX_CONTINUATIONS):
        response = await _client().beta.messages.create(
            model=settings.claude_model,
            max_tokens=8000,
            messages=messages,
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}],
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason != "pause_turn":
            break
        # A pesquisa continua no servidor: reenviamos a conversa com o turno pausado.
        messages = messages[:1] + [{"role": "assistant", "content": response.content}]
    if response is None or response.stop_reason == "refusal":
        return "The search could not be completed."
    text = " ".join(b.text for b in response.content if b.type == "text").strip()
    return text or "No results found."
