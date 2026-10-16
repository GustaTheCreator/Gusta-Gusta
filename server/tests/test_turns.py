import asyncio

import pytest
from pipecat.frames.frames import (
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.utils.asyncio.task_manager import TaskManager

from jarvis.turns import PatientTurnStop, looks_unfinished


@pytest.mark.parametrize(
    "text, unfinished",
    [
        ("What's the weather in Lisbon?", False),
        ("Tell me about the news.", False),
        ("Tell me about the", True),
        ("And what about Benfica and.", True),
        ("I was thinking, um...", True),
        ("So what happened with,", True),
        ("Thanks", False),
        ("", False),
    ],
)
def test_looks_unfinished(text, unfinished):
    assert looks_unfinished(text) is unfinished


async def _run(texts: list[str], speech_timeout=0.05, extra=0.3):
    strategy = PatientTurnStop(user_speech_timeout=speech_timeout, unfinished_extra=extra)
    tm = TaskManager()
    await strategy.setup(type("Setup", (), {"task_manager": tm})())
    stopped = []

    @strategy.event_handler("on_user_turn_stopped")
    async def on_stopped(_strategy, _params):
        stopped.append(asyncio.get_running_loop().time())

    await strategy.handle_user_turn_started()
    t0 = asyncio.get_running_loop().time()
    for text in texts:
        await strategy.process_frame(VADUserStartedSpeakingFrame())
        await strategy.process_frame(VADUserStoppedSpeakingFrame(stop_secs=0.2))
        await strategy.process_frame(TranscriptionFrame(text, "u", "now", finalized=True))
    await asyncio.sleep(0.6)
    await strategy.cleanup()
    return [t - t0 for t in stopped]


@pytest.mark.asyncio
async def test_complete_sentence_ends_turn_quickly():
    stopped = await _run(["What's the weather like today?"])
    assert len(stopped) == 1 and stopped[0] < 0.2


@pytest.mark.asyncio
async def test_unfinished_sentence_waits_longer():
    stopped = await _run(["Tell me more about the"])
    assert len(stopped) == 1 and stopped[0] >= 0.3
