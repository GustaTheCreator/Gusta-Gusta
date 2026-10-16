"""Uma voz masculina por idioma; a ativa segue o idioma em que o Gustavo falou."""
from functools import cache

from piper import PiperVoice
from pipecat.frames.frames import Frame
from pipecat.pipeline.parallel_pipeline import ParallelPipeline
from pipecat.processors.filters.function_filter import FunctionFilter

from .config import settings
from .language import LanguageState


# O PiperTTSService carrega o modelo da voz no construtor (~3 s por voz), e o bot cria um novo
# a cada ligação. Guardando o modelo, só a primeira ligação (ou o arranque) paga esse custo.
PiperVoice.load = cache(PiperVoice.load)


def preload():
    """Carrega as duas vozes no arranque do servidor."""
    _make_tts("pt")
    _make_tts("en")


def _make_tts(lang: str):
    from pipecat.services.piper.tts import PiperTTSService

    return PiperTTSService(
        settings=PiperTTSService.Settings(
            voice=settings.piper_voice_pt if lang == "pt" else settings.piper_voice_en
        ),
        download_dir=settings.models_dir / "piper",
    )


class BilingualTTS(ParallelPipeline):
    def __init__(self, language_state: LanguageState):
        self._state = language_state

        async def speaks(lang: str) -> bool:
            return self._state.current == lang

        async def pt(_: Frame) -> bool:
            return await speaks("pt")

        async def en(_: Frame) -> bool:
            return await speaks("en")

        super().__init__(
            [FunctionFilter(pt), _make_tts("pt")],
            [FunctionFilter(en), _make_tts("en")],
        )
