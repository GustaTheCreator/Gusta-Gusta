"""Quando é que o Gustavo acabou de falar.

Só com silêncio, uma pausa a meio da frase ("what about the... um...") fecha a vez e o Gusta-Gusta
responde a meia pergunta. Aqui, se a transcrição parece a meio, espera-se mais um pouco.
"""
import re

from pipecat.turns.user_stop import SpeechTimeoutUserTurnStopStrategy

# Palavras que quase nunca acabam uma frase.
HANGING_WORDS = {
    "a", "an", "the", "and", "or", "but", "so", "because", "if", "then", "that", "which",
    "to", "of", "for", "with", "about", "from", "in", "on", "at", "by", "into", "like",
    "my", "your", "his", "her", "their", "our", "is", "are", "was", "were", "what", "who",
    "where", "when", "how", "why", "um", "uh", "erm", "er", "hmm", "also", "maybe", "just",
}


def looks_unfinished(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    if text.endswith(("...", "…", ",", "-", "—")):
        return True
    if text.endswith(("?", "!")):
        return False
    words = re.findall(r"[a-z']+", text.lower())
    return bool(words) and words[-1] in HANGING_WORDS


class PatientTurnStop(SpeechTimeoutUserTurnStopStrategy):
    """Fim de turno por silêncio, com uma espera extra quando a frase ficou a meio."""

    def __init__(self, *, user_speech_timeout: float, unfinished_extra: float, **kwargs):
        super().__init__(user_speech_timeout=user_speech_timeout, **kwargs)
        self._unfinished_extra = unfinished_extra
        self._extended = False

    async def _discard_pending_end_of_turn(self):
        # Corre quando a vez acaba ou quando ele volta a falar: a espera extra recomeça.
        self._extended = False
        await super()._discard_pending_end_of_turn()

    async def _maybe_trigger_user_turn_stopped(self):
        if self._vad_user_speaking or not self._text:
            return
        if not (self._user_speech_wait_done and self._stt_wait_done):
            return
        if not self._extended and looks_unfinished(self._text):
            self._extended = True
            self._user_speech_wait_done = False
            self._user_speech_timeout_task = self.task_manager.create_task(
                self._user_speech_timeout_handler(self._unfinished_extra),
                f"{self}::_unfinished_timeout_handler",
            )
            return
        await self.trigger_user_turn_stopped()
