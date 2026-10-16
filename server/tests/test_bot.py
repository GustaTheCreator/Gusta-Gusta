from pipecat.adapters.services.anthropic_adapter import AnthropicLLMAdapter
from pipecat.processors.aggregators.llm_context import LLMContext

from jarvis import bot
from jarvis.config import _whisper_model


def test_tools_exposed_to_claude():
    params = AnthropicLLMAdapter().get_llm_invocation_params(
        LLMContext(tools=bot.TOOLS), enable_prompt_caching=False, system_instruction="x"
    )
    tools = {t["name"]: t["input_schema"] for t in params["tools"]}
    assert set(tools) == {"get_news", "get_weather", "search_web", "recall_memory", "remember"}
    assert tools["remember"]["required"] == ["topic", "fact", "kind"]
    assert tools["recall_memory"]["required"] == ["topic"]


def test_system_prompt_includes_memory_and_is_english_only(monkeypatch):
    monkeypatch.setattr(bot.memory, "load_context", lambda: "About him:\n- Family: His mum is Ana.")
    prompt = bot.system_prompt()
    assert "His mum is Ana." in prompt
    assert "always speak English" in prompt and "Portuguese (Portugal" not in prompt


def test_english_only_whisper_models():
    assert _whisper_model("base") == "base.en"
    assert _whisper_model("small") == "small.en"
    assert _whisper_model("large-v3-turbo") == "large-v3-turbo"
    assert _whisper_model("small.en") == "small.en"
