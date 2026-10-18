"""A voz do Duarte (Piper, 100% local)."""
from functools import cache

from piper import PiperVoice

from .config import settings

# O PiperTTSService carrega o modelo da voz no construtor (~3 s), e o bot cria um novo
# a cada ligação. Guardando o modelo, só a primeira ligação (ou o arranque) paga esse custo.
PiperVoice.load = cache(PiperVoice.load)


def preload():
    """Carrega a voz no arranque do servidor."""
    make_tts()


def make_tts():
    from pipecat.services.piper.tts import PiperTTSService

    return PiperTTSService(
        settings=PiperTTSService.Settings(voice=settings.piper_voice),
        download_dir=settings.models_dir / "piper",
    )
