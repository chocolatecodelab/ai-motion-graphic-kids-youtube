"""Character Bible v2: Arka & Lipa IDs, with rig v1 (kai/needle) artifacts still loading."""

import pytest
from pydantic import TypeAdapter, ValidationError

from factory.resources import rig
from factory.schemas.characters import CharacterId, Focus
from factory.schemas.script import ScriptLine


def test_legacy_ids_upgrade_on_load():
    assert ScriptLine(speaker="kai", text="Hi!").speaker == "arka"
    assert ScriptLine(speaker="needle", text="Hi!").speaker == "lipa"
    assert TypeAdapter(Focus).validate_python("needle") == "lipa"
    assert TypeAdapter(Focus).validate_python("graphic") == "graphic"


def test_unknown_character_rejected():
    with pytest.raises(ValidationError):
        TypeAdapter(CharacterId).validate_python("bob")


def test_rig_v2_catalogue():
    r = rig()
    assert r.version == "rig.v2"
    assert set(r.characters) == {"arka", "lipa"}
    # look_up stays available so v1 storyboards keep a valid pose.
    assert {"idle", "talk", "walk", "hold_map", "look_out", "look_up"} <= r.ids("arka", "poses")
    assert {"float", "flap", "glide", "perch"} <= r.ids("lipa", "poses")
    assert "worried" in r.ids("arka", "expressions")
