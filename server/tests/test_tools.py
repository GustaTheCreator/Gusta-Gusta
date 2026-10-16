from types import SimpleNamespace

import httpx
import pytest

from jarvis.tools import memory, news, weather, web_search

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


class _FakeMessages:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    async def create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_web_search_resumes_pause_turn(monkeypatch):
    paused = SimpleNamespace(stop_reason="pause_turn", content=[SimpleNamespace(type="server_tool_use")])
    done = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="O Porto ganhou 2-1.")])
    fake = _FakeMessages([paused, done])
    monkeypatch.setattr(web_search, "_client", lambda: SimpleNamespace(beta=SimpleNamespace(messages=fake)))

    assert await web_search.search("Quem ganhou o jogo do Porto?") == "O Porto ganhou 2-1."
    assert fake.calls[0]["tools"][0]["type"] == "web_search_20260209"
    assert fake.calls[1]["messages"][1] == {"role": "assistant", "content": paused.content}
