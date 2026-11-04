"""Workflow v1 (M1 slice). Later stages are appended as they are built:

brief -> script -> script_validate (owner approval) -> storyboard (llm lane)
                                                  \\-> voice -> subtitles (media lane)
"""

from __future__ import annotations

from factory.agents.brief import BriefStage
from factory.agents.script import ScriptStage
from factory.agents.script_validate import ScriptValidateStage
from factory.agents.storyboard import StoryboardStage
from factory.agents.subtitles import SubtitlesStage
from factory.agents.voice import VoiceStage
from factory.media.stt import Transcriber
from factory.pipeline import Workflow
from factory.providers.llm import LLMProvider
from factory.providers.tts import TTSProvider

WORKFLOW_VERSION = "1"


def build_workflow(
    llm: LLMProvider, tts: TTSProvider | None = None, stt: Transcriber | None = None
) -> Workflow:
    return Workflow([
        BriefStage(),
        ScriptStage(llm),
        ScriptValidateStage(llm),
        StoryboardStage(llm),
        VoiceStage(tts, stt),
        SubtitlesStage(),
    ])
