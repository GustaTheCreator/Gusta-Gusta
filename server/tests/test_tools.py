from types import SimpleNamespace

import httpx
import pytest

from jarvis.tools import memory, news, weather

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>X</title>
<item><title>Governo aprova orçamento</title><description>Votado hoje.</description></item>
<item><title>Benfica vence</title><description>&lt;p&gt;html&lt;/p&gt;</description></item>
</channel></rss>""".encode()


def test_news_parses_feeds(monkeypatch):
    monkeypatch.setattr(news, "settings", SimpleNamespace(news_feeds=[("Teste", "https://x/rss")]))
    monkeypatch.setattr(
        news.httpx, "get", lambda *a, **k: httpx.Response(200, content=RSS, request=httpx.Request("GET", "https://x/rss"))
    )
    out = news.get_news()
    assert "## Teste" in out
    assert "- Governo aprova orçamento: Votado hoje." in out
    assert "- Benfica vence" in out and "<p>" not in out


def test_news_reports_feed_errors(monkeypatch):
    monkeypatch.setattr(news, "settings", SimpleNamespace(news_feeds=[("Teste", "https://x/rss")]))

    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(news.httpx, "get", boom)
    assert "could not fetch the feed" in news.get_news()


def test_weather_formats(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        if "geocoding" in url:
            body = {"results": [{"name": "Lisboa", "country": "Portugal", "latitude": 38.7, "longitude": -9.1}]}
        else:
            body = {
                "current": {"temperature_2m": 18.2, "apparent_temperature": 17.0, "weather_code": 2, "wind_speed_10m": 12},
                "daily": {"temperature_2m_min": [14, 13], "temperature_2m_max": [22, 20],
                          "precipitation_probability_max": [10, 60], "weather_code": [1, 63]},
            }
        return SimpleNamespace(json=lambda: body)

    monkeypatch.setattr(weather.httpx, "get", fake_get)
    out = weather.get_weather("Lisboa")
    assert "Lisboa (Portugal) now: 18.2°C" in out
    assert "Tomorrow: low 13°C, high 20°C, rain, chance of rain 60%." in out
