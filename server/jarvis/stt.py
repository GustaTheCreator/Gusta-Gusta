"""Whisper local, só em inglês."""
import asyncio
from collections.abc import AsyncGenerator

import numpy as np
from faster_whisper import WhisperModel
from loguru import logger

from pipecat.frames.frames import ErrorFrame, Frame, TranscriptionFrame
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.transcriptions.language import Language
from pipecat.utils.time import time_now_iso8601

from .config import settings

# Nomes que o Whisper costuma ouvir mal; o prompt inicial puxa-o para a grafia certa.
INITIAL_PROMPT = "Gusta-Gusta, Gustavo."

_models: dict[str, WhisperModel] = {}


def get_model(name: str) -> WhisperModel:
    # Carregado uma vez por processo e partilhado entre ligações.
    if name not in _models:
        _models[name] = WhisperModel(
            name,
            device="cpu",
            compute_type="int8",
            download_root=str(settings.models_dir / "whisper"),
        )
    return _models[name]


class EnglishWhisperSTT(WhisperSTTService):
    def __init__(self, **kwargs):
        super().__init__(
            settings=WhisperSTTService.Settings(
                model=settings.whisper_model,
                language=Language.EN,
                initial_prompt=INITIAL_PROMPT,
            ),
            device="cpu",
            compute_type="int8",
            **kwargs,
        )

    def _load(self):
        self._model = get_model(settings.whisper_model)

    def _transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self._model.transcribe(
            audio,
            language="en",
            beam_size=settings.whisper_beam_size,
            initial_prompt=INITIAL_PROMPT,
            condition_on_previous_text=False,
        )
        threshold = self._settings.no_speech_prob
        return " ".join(
            s.text.strip() for s in segments if threshold is None or s.no_speech_prob < threshold
        ).strip()

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        if not self._model:
            yield ErrorFrame("Whisper model not available")
            return
        await self.start_processing_metrics()
        audio_float = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        text = await asyncio.to_thread(self._transcribe, audio_float)
        await self.stop_processing_metrics()
        if not text:
            return
        logger.debug(f"Transcription: {text}")
        yield TranscriptionFrame(text, self._user_id, time_now_iso8601(), Language.EN)
