"""Manchetes do dia a partir de RSS (em português; o Claude resume-as em inglês)."""
import concurrent.futures as cf

import feedparser
import httpx

from ..config import settings

UA = {"User-Agent": "Mozilla/5.0 (Jarvis self-hosted)"}


def _fetch(name: str, url: str, limit: int) -> str:
    try:
        resp = httpx.get(url, headers=UA, timeout=8, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        return f"## {name}\n(could not fetch the feed: {exc.__class__.__name__})"
    feed = feedparser.parse(resp.content)
    lines = [f"## {name}"]
    for entry in feed.entries[:limit]:
        title = entry.get("title", "").strip()
        summary = entry.get("summary", "").strip()
        if "<" in summary:  # muitos feeds trazem HTML no resumo
            summary = ""
        lines.append(f"- {title}" + (f": {summary[:200]}" if summary else ""))
    return "\n".join(lines)


def get_news(per_source: int = 6) -> str:
    per_source = max(1, min(int(per_source), 15))
    with cf.ThreadPoolExecutor(max_workers=len(settings.news_feeds) or 1) as pool:
        parts = pool.map(lambda f: _fetch(f[0], f[1], per_source), settings.news_feeds)
        return "\n\n".join(parts)
