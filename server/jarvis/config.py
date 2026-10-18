"""Configuração lida do ambiente (.env)."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
# O SDK usa a subscrição (CLAUDE_CODE_OAUTH_TOKEN); uma chave da API na env passava à frente e cobrava por token.
os.environ.pop("ANTHROPIC_API_KEY", None)

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
    claude_model: str = _env("CLAUDE_MODEL", "claude-haiku-5-5")
    claude_effort: str = _env("CLAUDE_EFFORT", "low")
    # Modelo que revê a conversa no fim e decide o que guardar na memória.
    memory_model: str = _env("MEMORY_MODEL", _env("CLAUDE_MODEL", "claude-haiku-5-5"))

    whisper_model: str = _env("WHISPER_MODEL", "small")
    # 1 é o mais rápido; valores maiores percebem melhor mas demoram mais no CPU.
    whisper_beam_size: int = int(_env("WHISPER_BEAM_SIZE", "3"))
    models_dir: Path = Path(_env("MODELS_DIR", "./models"))
    memory_dir: Path = Path(_env("MEMORY_DIR", "./data/memory"))

    piper_voice: str = _env("PIPER_VOICE", "pt_PT-tugao-medium")

    default_city: str = _env("DEFAULT_CITY", "Lisbon")
    news_feeds: list[tuple[str, str]] = field(
        default_factory=lambda: _feeds(_env("NEWS_FEEDS", DEFAULT_FEEDS))
    )

    host: str = _env("HOST", "0.0.0.0")
    port: int = int(_env("PORT", "7860"))
    web_dir: Path = Path(_env("WEB_DIR", "../web/dist"))


settings = Settings()
