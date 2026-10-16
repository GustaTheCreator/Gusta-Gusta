"""Configuração lida do ambiente (.env)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_FEEDS = (
    "Público|https://feeds.feedburner.com/PublicoRSS,"
    "Observador|https://observador.pt/feed/,"
    "RTP|https://www.rtp.pt/noticias/rss,"
    "Expresso|https://expresso.pt/rss"
)


def _feeds(raw: str) -> list[tuple[str, str]]:
    feeds = []
    for item in raw.split(","):
        name, _, url = item.strip().partition("|")
        if url.strip():
            feeds.append((name.strip(), url.strip()))
    return feeds


def _env(name: str, default: str) -> str:
    return os.getenv(name) or default


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = _env("CLAUDE_MODEL", "claude-opus-5-5")
    claude_effort: str = _env("CLAUDE_EFFORT", "low")

    whisper_model: str = _env("WHISPER_MODEL", "base")
    models_dir: Path = Path(_env("MODELS_DIR", "./models"))
    memory_dir: Path = Path(_env("MEMORY_DIR", "./data/memory"))

    piper_voice_en: str = _env("PIPER_VOICE_EN", "en_GB-alan-medium")
    piper_voice_pt: str = _env("PIPER_VOICE_PT", "pt_PT-tugao-medium")

    default_language: str = _env("DEFAULT_LANGUAGE", "pt")
    default_city: str = _env("DEFAULT_CITY", "Lisboa")
    news_feeds: list[tuple[str, str]] = field(
        default_factory=lambda: _feeds(_env("NEWS_FEEDS", DEFAULT_FEEDS))
    )

    host: str = _env("HOST", "0.0.0.0")
    port: int = int(_env("PORT", "7860"))
    web_dir: Path = Path(_env("WEB_DIR", "../web/dist"))


settings = Settings()
