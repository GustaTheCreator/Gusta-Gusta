"""Idioma da conversa: detetado no que o Gustavo diz e usado para escolher a voz."""
from dataclasses import dataclass

SUPPORTED = ("pt", "en")


@dataclass
class LanguageState:
    current: str = "pt"


def pick_language(detected: str | None, probabilities: list[tuple[str, float]] | None) -> str | None:
    """Restringe a deteção do Whisper a português ou inglês.

    Devolve None se o idioma detetado já for suportado, ou o suportado mais provável
    quando o Whisper achar que é outro (frases curtas confundem-no com galego, espanhol...).
    """
    if detected in SUPPORTED:
        return None
    probs = dict(probabilities or [])
    return max(SUPPORTED, key=lambda lang: probs.get(lang, 0.0))
