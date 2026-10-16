from types import SimpleNamespace

import pytest

from jarvis import curator
from jarvis.tools import memory


@pytest.fixture(autouse=True)
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "settings", SimpleNamespace(memory_dir=tmp_path))
    return tmp_path


MESSAGES = [
    {"role": "user", "content": "(It is Friday 16 October 2026, 08:00. Gustavo just opened the app.)"},
    {"role": "assistant", "content": "Good morning, Gustavo."},
    {"role": "user", "content": "What's the news today?"},
    {"role": "assistant", "content": [{"type": "text", "text": "The budget passed and the metro is on strike."}]},
    {"role": "assistant", "tool_calls": [{"id": "1"}]},
    {"role": "tool", "content": "raw headlines"},
    {"role": "user", "content": "Tell me more about the metro strike."},
]


def test_transcript_skips_greeting_and_tools():
    text = curator.transcript(MESSAGES)
    assert text.splitlines() == [
        "Gusta-Gusta: Good morning, Gustavo.",
        "Gustavo: What's the news today?",
        "Gusta-Gusta: The budget passed and the metro is on strike.",
        "Gustavo: Tell me more about the metro strike.",
    ]


class _FakeMessages:
    def __init__(self, review):
        self.review, self.calls = review, []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", parsed_output=self.review)


@pytest.mark.asyncio
async def test_review_applies_updates_and_skips_routine(vault, monkeypatch):
    review = curator.Review(
        updates=[
            curator.Update(topic="Lisbon metro strike", kind="interest",
                           facts=["He wanted to know how long the metro strike lasts."]),
            curator.Update(topic="Today's news", kind="fact", facts=["He asked for the news."]),
        ],
        candidates=[curator.Candidate(topic="State budget", detail="He heard about the budget.")],
    )
    fake = _FakeMessages(review)
    monkeypatch.setattr(curator, "_client", lambda: SimpleNamespace(messages=fake))

    await curator.review(MESSAGES)

    assert fake.calls[0]["output_format"] is curator.Review
    assert "Tell me more about the metro strike." in fake.calls[0]["messages"][0]["content"]
    assert memory.find("Lisbon metro strike").kind == "interest"
    assert memory.find("Today's news") is None
    assert memory.find("State budget") is None  # só candidato, por agora
    assert (vault / ".jarvis" / "candidates.json").exists()


@pytest.mark.asyncio
async def test_review_skips_empty_conversations(monkeypatch):
    fake = _FakeMessages(None)
    monkeypatch.setattr(curator, "_client", lambda: SimpleNamespace(messages=fake))
    await curator.review(MESSAGES[:2])
    assert fake.calls == []
