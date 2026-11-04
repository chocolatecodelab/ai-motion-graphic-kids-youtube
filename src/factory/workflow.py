"""Workflow v1 (M1 slice). Later stages are appended as they are built:

brief -> script -> script_validate (owner approval) -> storyboard ---------------\\
                                                  \\-> voice -> subtitles --------> timing
timing -> render_scenes (render lane) -> assemble (media lane) -> episode MP4
"""

from __future__ import annotations

from factory.agents.assemble import AssembleStage
from factory.agents.brief import BriefStage
from factory.agents.render import RenderScenesStage
from factory.agents.script import ScriptStage
from factory.agents.script_validate import ScriptValidateStage
from factory.agents.storyboard import StoryboardStage
from factory.agents.subtitles import SubtitlesStage
from factory.agents.timing import TimingStage
from factory.agents.voice import VoiceStage
from factory.media.stt import Transcriber
from factory.pipeline import Workflow
from factory.providers.llm import LLMProvider
from factory.providers.tts import TTSProvider

WORKFLOW_VERSION = "1"


def build_workflow(
    llm: LLMProvider, tts: TTSProvider | None = None, stt: Transcriber | None = None,
    render_stage: RenderScenesStage | None = None,
) -> Workflow:
    return Workflow([
        BriefStage(),
        ScriptStage(llm),
        ScriptValidateStage(llm),
        StoryboardStage(llm),
        VoiceStage(tts, stt),
        SubtitlesStage(),
        TimingStage(),
        render_stage or RenderScenesStage(),
        AssembleStage(),
    ])
