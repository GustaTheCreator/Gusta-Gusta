"""Whisper local que deteta se falas português ou inglês."""
import asyncio
from collections.abc import AsyncGenerator

import numpy as np
from faster_whisper import WhisperModel
from loguru import logger

from pipecat.frames.frames import ErrorFrame, Frame, TranscriptionFrame
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.utils.time import time_now_iso8601

from .config import settings
from .language import LanguageState, pick_language

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


class BilingualWhisperSTT(WhisperSTTService):
    def __init__(self, language_state: LanguageState, **kwargs):
        self._language_state = language_state
        super().__init__(
            settings=WhisperSTTService.Settings(model=settings.whisper_model, language=None),
            device="cpu",
            compute_type="int8",
            **kwargs,
        )

    def _load(self):
        self._model = get_model(settings.whisper_model)

    def _transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        segments, info = self._model.transcribe(audio, language=None, beam_size=1)
        segments = list(segments)
        forced = pick_language(info.language, info.all_language_probs)
        if forced:
            segments, _ = self._model.transcribe(audio, language=forced, beam_size=1)
            segments = list(segments)
        threshold = self._settings.no_speech_prob
        text = " ".join(
            s.text.strip() for s in segments if threshold is None or s.no_speech_prob < threshold
        )
        return text.strip(), forced or info.language

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        if not self._model:
            yield ErrorFrame("Whisper model not available")
            return
        await self.start_processing_metrics()
        audio_float = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        text, language = await asyncio.to_thread(self._transcribe, audio_float)
        await self.stop_processing_metrics()
        if not text:
            return
        self._language_state.current = language
        logger.debug(f"Transcription [{language}]: {text}")
        yield TranscriptionFrame(text, self._user_id, time_now_iso8601(), language)
