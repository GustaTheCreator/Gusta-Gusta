"""Uma voz masculina por idioma; a ativa segue o idioma em que o Gustavo falou."""
from pipecat.frames.frames import Frame
from pipecat.pipeline.parallel_pipeline import ParallelPipeline
from pipecat.processors.filters.function_filter import FunctionFilter
from pipecat.transcriptions.language import Language

from .config import settings
from .language import LanguageState


def _make_tts(lang: str):
    if settings.tts_provider == "azure":
        from pipecat.services.azure.tts import AzureTTSService

        return AzureTTSService(
            api_key=settings.azure_speech_key,
            region=settings.azure_speech_region,
            settings=AzureTTSService.Settings(
                voice=settings.azure_voice_pt if lang == "pt" else settings.azure_voice_en,
                language=Language.PT_PT if lang == "pt" else Language.EN_GB,
                effect=None,
            ),
        )
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
