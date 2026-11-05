"""visual_plan + assets (M2): SVG sanitizer, asset library, plan checks, retries."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest

from factory.agents.assets import AssetsStage
from factory.agents.visual_plan import check_visual_plan
from factory.assetlib import AssetLibrary, sanitize_svg
from factory.config import Settings
from factory.pipeline import PermanentStageError, StageContext
from factory.providers.llm.fake import FakeLLM
from factory.schemas.storyboard import Storyboard
from factory.schemas.visual import VisualPlan, VisualPlanDraft
from helpers import GOOD_SVG, visual_plan_for

# ------------------------------------------------------------------ sanitizer


def test_good_svg_passes_and_is_reserialised() -> None:
    clean, problems = sanitize_svg(GOOD_SVG)
    assert problems == []
    assert clean.startswith("<svg") and 'viewBox="0 0 400 400"' in clean


@pytest.mark.parametrize(("bad", "needle"), [
    ('<text x="10" y="20" stroke="#2B2240">HELLO</text>', "<text>"),
    ("<script>alert(1)</script>", "<script>"),
    ('<image href="http://x/y.png"/>', "<image>"),
    ('<foreignObject><div/></foreignObject>', "<foreignObject>"),
    ('<rect x="0" y="0" width="5" height="5" style="fill:red"/>', "'style'"),
    ('<rect x="0" y="0" width="5" height="5" onclick="x()"/>', "'onclick'"),
    ('<rect x="0" y="0" width="5" height="5" fill="url(http://evil/x)"/>', "internal url"),
])
def test_dangerous_content_is_rejected(bad: str, needle: str) -> None:
    svg = GOOD_SVG.replace("</svg>", bad + "</svg>")
    clean, problems = sanitize_svg(svg)
    assert any(needle in p for p in problems), problems
    assert "<text" not in clean and "script" not in clean and "onclick" not in clean


def test_entities_and_bad_xml_rejected() -> None:
    assert sanitize_svg('<!DOCTYPE svg [<!ENTITY a "b">]><svg/>')[1]
    assert sanitize_svg("<svg viewBox='0 0 400 400'><path></svg>")[1]


def test_style_rules_ink_outline_and_palette() -> None:
    no_ink = GOOD_SVG.replace('stroke="#2B2240"', 'stroke="#D2A040"')
    assert any("house ink" in p for p in sanitize_svg(no_ink)[1])
    neon = GOOD_SVG.replace("#D2A040", "#00FF00").replace("#4E92D6", "#FF00FF").replace(
        "#A6772A", "#00FFFF").replace("#9A6438", "#FF0088")
    assert any("off-palette" in p for p in sanitize_svg(neon)[1])


# ------------------------------------------------------------------ library


def test_library_add_dedupes_and_finds_by_name(tmp_path: Path) -> None:
    lib = AssetLibrary(tmp_path)
    clean, _ = sanitize_svg(GOOD_SVG)
    a = lib.add("Brass Telescope", ["space"], clean, "fake:model", "prompt", "ep-1")
    b = lib.add("other name", [], clean, "fake:model", "prompt", "ep-2")
    assert a.asset_id == b.asset_id and len(lib.records()) == 1  # same content -> same asset
    assert lib.find("the brass telescope").asset_id == a.asset_id
    assert lib.svg(a.asset_id) == clean
    assert a.licence.startswith("original") and a.generator == "fake:model"


# ------------------------------------------------------------------ plan checks


def _board(ids: list[str]) -> Storyboard:
    return Storyboard.model_construct(scenes=[type("S", (), {"scene_id": i})() for i in ids])


def test_plan_checks_catch_centre_props_unknown_refs_and_bad_requests(tmp_path: Path) -> None:
    ids = ["S01", "S02"]
    draft = VisualPlanDraft.model_validate(visual_plan_for(ids))
    assert check_visual_plan(draft, _board(ids), AssetLibrary(tmp_path)) == []
    bad = visual_plan_for(ids)
    bad["scenes"][1]["props"] = [{"ref": "builtin:tree", "x": 0.5, "y": 0.93, "depth": "near"},
                                 {"ref": "builtin:unicorn", "x": 0.1, "y": 0.93},
                                 {"ref": "asset:nope", "x": 0.9, "y": 0.93}]
    bad["asset_requests"].append({"request_id": "sign_text", "name": "sign",
                                  "description": "a sign with text on it"})
    issues = check_visual_plan(VisualPlanDraft.model_validate(bad), _board(ids),
                               AssetLibrary(tmp_path))
    text = " ".join(issues)
    assert "would stand where the characters are" in text
    assert "unknown built-in prop 'unicorn'" in text and "unknown library asset 'nope'" in text
    assert "never placed" in text and "no characters, text or brands" in text


# ------------------------------------------------------------------ assets stage


def _ctx(tmp_path: Path, plan: VisualPlan) -> StageContext:
    s = Settings(content_dir=tmp_path / "content", library_dir=tmp_path / "library")
    path = tmp_path / "content" / "ep" / "visual_plan" / "plan.json"
    path.parent.mkdir(parents=True)
    path.write_text(plan.model_dump_json(), encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return StageContext(episode_id=uuid.uuid4(), job_id=uuid.uuid4(), stage="assets", attempt=1,
                        settings=s, workdir=tmp_path / "content" / "ep" / "assets",
                        upstream={"visual_plan": {"path": "ep/visual_plan/plan.json",
                                                  "sha256": digest}})


def _plan() -> VisualPlan:
    d = VisualPlanDraft.model_validate(visual_plan_for(["S01"]))
    return VisualPlan(episode_slug="ep", storyboard_version=1, scenes=d.scenes,
                      asset_requests=d.asset_requests, prop_catalogue_version="props.v1")


def test_assets_retries_with_feedback_then_stores(tmp_path: Path) -> None:
    bad = GOOD_SVG.replace("</svg>", "<text>hi</text></svg>")
    llm = FakeLLM([{"svg": bad}, {"svg": GOOD_SVG}])
    out = AssetsStage(llm).run(_ctx(tmp_path, _plan())).output_refs
    assert out["generated"] == 1 and out["reused"] == 0
    assert "<text> is not allowed" in llm.requests[1].prompt  # feedback reached the model
    lib = AssetLibrary(tmp_path / "library")
    assert len(lib.records()) == 1 and lib.records()[0].source_episode == "ep"


def test_assets_reuses_library_and_gives_up_after_three(tmp_path: Path) -> None:
    lib = AssetLibrary(tmp_path / "library")
    lib.add("brass telescope", [], sanitize_svg(GOOD_SVG)[0], "fake:m", "p", "old-ep")
    out = AssetsStage(FakeLLM([])).run(_ctx(tmp_path, _plan())).output_refs
    assert out["reused"] == 1 and out["generated"] == 0

    bad = {"svg": "<svg viewBox='0 0 400 400'><text>x</text></svg>"}
    with pytest.raises(PermanentStageError, match="failed the style checks 3 times"):
        AssetsStage(FakeLLM([bad, bad, bad])).run(_ctx(tmp_path / "b", _plan()))
