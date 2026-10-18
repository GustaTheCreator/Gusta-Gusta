from jarvis import bot, brain


def test_tools_exposed_to_claude():
    assert {t.name for t in brain.TOOLS} == {"get_news", "get_weather", "recall_memory", "remember"}
    assert "WebSearch" in brain.ALLOWED and "mcp__jarvis__remember" in brain.ALLOWED
    assert brain.voice_options("x").tools == ["WebSearch"]


def test_system_prompt_includes_memory_and_is_portuguese_only(monkeypatch):
    monkeypatch.setattr(bot.memory, "load_context", lambda: "About him:\n- Family: His mum is Ana.")
    prompt = bot.system_prompt()
    assert "His mum is Ana." in prompt
    assert "always speak European Portuguese" in prompt and "always speak English" not in prompt
