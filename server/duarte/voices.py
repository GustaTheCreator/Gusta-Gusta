"""A voz do Duarte: ElevenLabs se houver chave, senão Piper (100% local)."""
from functools import cache

from piper import PiperVoice

from .config import settings

# O PiperTTSService carrega o modelo da voz no construtor (~3 s), e o bot cria um novo
# a cada ligação. Guardando o modelo, só a primeira ligação (ou o arranque) paga esse custo.
PiperVoice.load = cache(PiperVoice.load)


def preload():
    """Carrega a voz Piper no arranque (é também a reserva se o ElevenLabs não estiver configurado)."""
    _piper()


def make_tts():
    if settings.elevenlabs_api_key:
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

        return ElevenLabsTTSService(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
            model=settings.elevenlabs_model,
        )
    return _piper()


def _piper():
    from pipecat.services.piper.tts import PiperTTSService

    return PiperTTSService(
        settings=PiperTTSService.Settings(voice=settings.piper_voice),
        download_dir=settings.models_dir / "piper",
    )
