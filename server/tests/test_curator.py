from types import SimpleNamespace

import pytest
from claude_agent_sdk import ResultMessage

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


def _fake_query(review, calls):
    async def query(*, prompt, options):
        calls.append((prompt, options))
        if review is not None:
            yield ResultMessage(
                subtype="success", duration_ms=0, duration_api_ms=0, is_error=False, num_turns=1,
                session_id="s", structured_output=review.model_dump(),
            )

    return query


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
    calls = []
    monkeypatch.setattr(curator, "query", _fake_query(review, calls))

    await curator.review(MESSAGES)

    prompt, options = calls[0]
    assert options.output_format["schema"] == curator.Review.model_json_schema()
    assert options.tools == []
    assert "Tell me more about the metro strike." in prompt
    assert memory.find("Lisbon metro strike").kind == "interest"
    assert memory.find("Today's news") is None
    assert memory.find("State budget") is None  # só candidato, por agora
    assert (vault / ".jarvis" / "candidates.json").exists()


@pytest.mark.asyncio
async def test_review_skips_empty_conversations(monkeypatch):
    calls = []
    monkeypatch.setattr(curator, "query", _fake_query(None, calls))
    await curator.review(MESSAGES[:2])
    assert calls == []
