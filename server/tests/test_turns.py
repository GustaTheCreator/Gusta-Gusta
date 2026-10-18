import asyncio

import pytest
from pipecat.frames.frames import (
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.utils.asyncio.task_manager import TaskManager

from duarte.turns import PatientTurnStop, looks_unfinished


@pytest.mark.parametrize(
    "text, unfinished",
    [
        ("Qual é o tempo em Lisboa?", False),
        ("Fala-me das notícias.", False),
        ("Fala-me das", True),
        ("E o que se passa com o Benfica e.", True),
        ("Estava a pensar, hum...", True),
        ("Então o que aconteceu com,", True),
        ("Obrigado", False),
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
    stopped = await _run(["Como está o tempo hoje?"])
    assert len(stopped) == 1 and stopped[0] < 0.2


@pytest.mark.asyncio
async def test_unfinished_sentence_waits_longer():
    stopped = await _run(["Fala-me mais sobre o"])
    assert len(stopped) == 1 and stopped[0] >= 0.3
