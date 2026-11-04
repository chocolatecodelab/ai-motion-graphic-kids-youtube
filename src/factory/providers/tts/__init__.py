from __future__ import annotations

from factory.config import Settings
from factory.providers.tts.base import TTSInfo, TTSProvider, TTSResult, WordTiming


def get_tts(settings: Settings) -> TTSProvider:
    if settings.tts_provider == "kokoro":
        from factory.providers.tts.kokoro import KokoroTTS

        return KokoroTTS()
    raise ValueError(f"unsupported tts_provider {settings.tts_provider!r}")


__all__ = ["TTSInfo", "TTSProvider", "TTSResult", "WordTiming", "get_tts"]
