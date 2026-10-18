from types import SimpleNamespace

from duarte import voices


def test_elevenlabs_when_key_set(monkeypatch):
    monkeypatch.setattr(
        voices, "settings",
        SimpleNamespace(elevenlabs_api_key="k", elevenlabs_voice_id="v", elevenlabs_model="eleven_flash_v2_5"),
    )
    assert type(voices.make_tts()).__name__ == "ElevenLabsTTSService"


def test_piper_without_key(monkeypatch):
    monkeypatch.setattr(voices, "_piper", lambda: "piper")
    monkeypatch.setattr(voices, "settings", SimpleNamespace(elevenlabs_api_key=""))
    assert voices.make_tts() == "piper"
