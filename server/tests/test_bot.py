import pytest
from pipecat.adapters.services.anthropic_adapter import AnthropicLLMAdapter
from pipecat.processors.aggregators.llm_context import LLMContext

from jarvis import bot, voices
from jarvis.language import LanguageState, pick_language


def test_pick_language_keeps_pt_and_en():
    assert pick_language("pt", [("pt", 0.9)]) is None
    assert pick_language("en", [("en", 0.8)]) is None


def test_pick_language_maps_other_languages_to_closest():
    # Frases curtas em português são muitas vezes detetadas como galego ou espanhol.
    assert pick_language("gl", [("gl", 0.5), ("pt", 0.3), ("en", 0.1)]) == "pt"
    assert pick_language("de", [("de", 0.4), ("en", 0.35), ("pt", 0.05)]) == "en"
    assert pick_language("xx", None) == "pt"


def test_tools_exposed_to_claude():
    params = AnthropicLLMAdapter().get_llm_invocation_params(
        LLMContext(tools=bot.TOOLS), enable_prompt_caching=False, system_instruction="x"
    )
    tools = {t["name"]: t["input_schema"] for t in params["tools"]}
    assert set(tools) == {"get_news", "get_weather", "search_web", "save_memory"}
    assert tools["save_memory"]["required"] == ["topic", "fact"]


def test_system_prompt_includes_memory(monkeypatch):
    monkeypatch.setattr(bot.memory, "load_context", lambda: "# Família\n- A mãe chama-se Ana.")
    prompt = bot.system_prompt()
    assert "A mãe chama-se Ana." in prompt and "European Portuguese" in prompt


@pytest.mark.asyncio
async def test_bilingual_tts_routes_by_language(monkeypatch):
    monkeypatch.setattr(voices, "_make_tts", lambda lang: voices.FunctionFilter(lambda f: True))
    state = LanguageState("pt")
    tts = voices.BilingualTTS(state)
    pt_filter, en_filter = (branch.processors[1] for branch in tts._pipelines)
    assert await pt_filter._filter(None) and not await en_filter._filter(None)
    state.current = "en"
    assert not await pt_filter._filter(None) and await en_filter._filter(None)
