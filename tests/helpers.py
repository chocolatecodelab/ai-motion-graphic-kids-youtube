"""Fixture builders shared by agent tests (imported as a plain module by pytest)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "config" / "pilots" / "why-is-the-sky-blue.yaml"


def pilot_brief_dict(min_s: int = 30, max_s: int = 60) -> dict[str, Any]:
    data = yaml.safe_load(PILOT.read_text(encoding="utf-8"))
    data["duration"] = {"min_s": min_s, "max_s": max_s}
    return data


def write_brief(path: Path, **kw: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(pilot_brief_dict(**kw), sort_keys=False), encoding="utf-8")
    return path


def L(speaker: str, text: str, claims: list[str] | None = None,  # noqa: N802
      emotion: str = "curious") -> dict[str, Any]:
    return {"speaker": speaker, "text": text, "emotion": emotion,
            "claim_ids": claims or [], "direction": ""}


def good_draft() -> dict[str, Any]:
    scenes = [
        ("hook", "Arka's attic", [
            L("arka", "Why is the sky blue, and not green or purple?"),
            L("lipa", "Ooh! I want to know too!", emotion="excited"),
        ]),
        ("mystery", "Attic window", [
            L("arka", "Sunlight looks white, but it hides every color of the rainbow.", ["C01"]),
            L("lipa", "So where do the other colors go?", emotion="puzzled"),
        ]),
        ("adventure", "Inside a sunbeam", [
            L("arka", "Okay, Lipa, show me the inside!", emotion="determined"),
            L("lipa", "Shrinking us down now. Hold on to your hat!", emotion="playful"),
            L("arka", "Light moves in waves. Each color has its own size of wave.", ["C02"]),
        ]),
        ("discovery", "High in the air", [
            L("arka", "Blue waves are short. Red waves are long.", ["C03"]),
            L("arka", "Tiny air bits bounce blue light all over the sky.", ["C04", "C05"]),
            L("lipa", "Boing, boing, boing! Blue everywhere!", emotion="delighted"),
        ]),
        ("twist", "A hologram of Mars", [
            L("arka", "On Mars, the daytime sky looks orange instead.", ["C08"],
              emotion="surprised"),
        ]),
        ("takeaway", "Back in the attic", [
            L("arka", "Blue bounces the most, so our sky looks blue.", ["C05"]),
            L("lipa", "Mystery solved!", emotion="delighted"),
            L("arka", "Almost! Next time, let's chase a sunset.", emotion="playful"),
        ]),
    ]
    return {
        "title_working": "Why Is the Sky Blue?",
        "learning_objectives": ["Sunlight is a mix of colors.",
                                "Air scatters blue light the most."],
        "scenes": [
            {"key": f"S{i:02d}", "beat": beat, "location": loc, "summary": f"{beat} scene",
             "lines": lines, "sound_cues": ["soft whoosh"], "visual_opportunities": ["rays"]}
            for i, (beat, loc, lines) in enumerate(scenes, start=1)
        ],
    }


def pass_review() -> dict[str, Any]:
    return {
        "scores": {"safety": 5, "age_appropriateness": 5, "accuracy": 4, "clarity": 4,
                   "story": 4, "character_voice": 4},
        "issues": [{"severity": "minor", "category": "clarity", "line_id": "S04-L02",
                    "detail": "'air bits' could say 'air molecules' once.",
                    "suggestion": "Add the word molecules."}],
        "unsupported_statements": [],
        "summary": "Safe, accurate and fun.",
    }


SHOT_CYCLE = [  # (type, angle, camera move, arka x, lipa x, arka motion)
    ("wide", "eye_level", "dolly_in", 0.45, 0.62, "walk"),
    ("medium", "low", "zoom_in", 0.55, 0.40, "none"),
    ("close_up", "high", "static", 0.50, 0.70, "none"),
    ("over_shoulder", "eye_level", "pan_right", 0.30, 0.55, "none"),
    ("extreme_wide", "birds_eye", "zoom_out", 0.60, 0.45, "fly"),
    ("medium", "tilted", "shake", 0.48, 0.35, "jump"),
]


def storyboard_for(script: Any, pad: float = 1.0) -> dict[str, Any]:
    scenes = []
    for i, scene in enumerate(script.draft.scenes):
        lines = [ln for ln in script.lines if ln.scene_key == scene.key]
        speakers = {ln.speaker for ln in lines}
        shot_type, angle, move, kx, nx, kmotion = SHOT_CYCLE[i % len(SHOT_CYCLE)]
        blocking = [{"character": "arka", "x": kx, "y": 0.9, "scale": 1.0, "pose": "talk",
                     "expression": "curious", "motion": kmotion}]
        if "lipa" in speakers:
            blocking.append({"character": "lipa", "x": nx, "y": 0.5, "scale": 0.6,
                             "depth": "foreground", "pose": "float",
                             "expression": "delighted", "motion": "zip",
                             "path": [{"x": nx + 0.1, "y": 0.4, "scale": 0.6}]})
        chars = [{"shot_type": shot_type, "angle": angle, "camera_move": move,
                  "focus": "both", "blocking": blocking}]
        mg = []
        if scene.beat == "discovery":
            mg.append({"component": "WaveCompare", "props": {"waves": ["blue", "red"]},
                       "at_line": lines[0].line_id})
        scenes.append({
            "scene_id": scene.key, "beat": scene.beat, "objective": scene.summary,
            "duration_s": round(sum(ln.est_duration_s + 0.35 for ln in lines) + pad, 2),
            "line_ids": [ln.line_id for ln in lines], "shots": chars,
            "background": {"theme": "attic", "asset_request": f"flat vector {scene.location}"},
            "motion_graphics": mg,
            "transition_out": {"type": "compass_portal" if scene.beat == "adventure" else "cut"},
            "educational_purpose": "understand the idea",
        })
    return {"scenes": scenes}
