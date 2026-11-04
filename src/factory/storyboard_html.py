"""Human-readable storyboard review page (self-contained HTML, works from file://).

Shows, per scene: a 16:9 layout sketch (background, character positions, graphics,
camera, transition), the dialogue with speakers and claim badges, every motion
graphic with its props, sound effects and the educational purpose. A timeline strip
and a claims/sources legend help the owner check pacing and accuracy at a glance.
"""

from __future__ import annotations

import json
from html import escape

from factory.schemas.brief import TopicBrief
from factory.schemas.script import Script
from factory.schemas.storyboard import Storyboard, StoryboardScene

BEAT_COLORS = {  # brand palette
    "hook": "#243B75", "mystery": "#3B6E8F", "adventure": "#55BBA5",
    "discovery": "#2F8F7A", "twist": "#F47C45", "takeaway": "#E0A928",
}
SPEAKER_COLORS = {"arka": "#2E9E7F", "lipa": "#FFD872"}
CAMERA_ICONS = {"static": "■", "push_in": "⤢ in", "pull_out": "⤡ out", "pan": "⇄",
                "parallax": "≋", "orbit": "↻"}

CSS = """
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;
background:#F4F0E8;color:#1d2b4f}header{background:#243B75;color:#fff;padding:24px 32px}
header h1{margin:0 0 4px;font-size:26px}header .meta{opacity:.85;font-size:14px}
main{max-width:1180px;margin:0 auto;padding:24px 20px 60px}
.timeline{display:flex;height:34px;border-radius:8px;overflow:hidden;margin:8px 0 6px;
box-shadow:0 1px 3px #0002}.timeline a{color:#fff;font-size:12px;font-weight:600;
display:flex;align-items:center;justify-content:center;text-decoration:none;
border-right:2px solid #F4F0E8;overflow:hidden;white-space:nowrap}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;margin-bottom:22px}
.legend span{display:inline-flex;align-items:center;gap:5px}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.scene{background:#fff;border-radius:14px;box-shadow:0 1px 4px #0002;margin:0 0 22px;
display:grid;grid-template-columns:440px 1fr;gap:20px;padding:18px;scroll-margin-top:12px}
@media(max-width:900px){.scene{grid-template-columns:1fr}}
.head{grid-column:1/-1;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.badge{color:#fff;border-radius:999px;padding:3px 10px;font-size:12px;font-weight:700;
text-transform:uppercase;letter-spacing:.04em}.sid{font-size:20px;font-weight:800}
.dur{font-size:13px;color:#555}.obj{color:#333;font-size:14px}
.frame{position:relative;aspect-ratio:16/9;border-radius:10px;overflow:hidden;
color:#fff;font-size:11px}.frame .bg{position:absolute;inset:0;padding:8px 96px 8px 10px;
background:linear-gradient(180deg,rgba(0,0,0,.05),rgba(0,0,0,.35));line-height:1.35}
.frame .bg em{opacity:.92}.char{position:absolute;bottom:10%;width:22%;text-align:center;
border-radius:10px;padding:6px 4px;color:#1d2b4f;font-weight:700;box-shadow:0 2px 6px #0004}
.char small{display:block;font-weight:500;font-size:10px}
.mg{position:absolute;top:30%;left:50%;transform:translateX(-50%);display:flex;gap:4px;
flex-wrap:wrap;justify-content:center;max-width:70%}.mg span{background:rgba(255,255,255,.92);
color:#243B75;border-radius:6px;padding:2px 6px;font-weight:700}
.cam{position:absolute;top:8px;right:10px;background:rgba(0,0,0,.45);border-radius:6px;
padding:2px 6px}.trans{position:absolute;bottom:8px;right:10px;background:rgba(0,0,0,.45);
border-radius:6px;padding:2px 6px}
.lines{list-style:none;margin:0 0 10px;padding:0}.lines li{padding:6px 0;
border-bottom:1px dashed #e4ded2;font-size:15px;line-height:1.4}
.who{font-weight:800;margin-right:6px}.emo{font-size:11px;color:#777;margin-right:6px}
.dir{display:block;font-size:12px;color:#888;font-style:italic}
.lid{font-size:11px;color:#999;margin-right:6px;font-family:ui-monospace,Consolas,monospace}
.claim{background:#EEF4FF;color:#243B75;border-radius:5px;padding:1px 5px;font-size:11px;
font-weight:700;margin-left:4px;text-decoration:none}.est{font-size:11px;color:#999}
audio.vo{display:block;height:28px;width:100%;max-width:320px;margin-top:4px}
video.clip{width:100%;aspect-ratio:16/9;border-radius:10px;background:#000;display:block}
h4{margin:12px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#666}
.kv{font-size:13px;color:#333}.kv code{background:#f5f2ec;padding:1px 4px;border-radius:4px;
font-size:12px;word-break:break-word}.ill{background:#FFF3D6;color:#8a5a00;border-radius:5px;
padding:1px 6px;font-size:11px;font-weight:700;margin-left:4px}
.purpose{background:#EAF7F3;border-left:4px solid #55BBA5;padding:8px 10px;border-radius:6px;
font-size:14px;margin-top:10px}.claims{background:#fff;border-radius:14px;padding:18px;
box-shadow:0 1px 4px #0002}.claims li{margin:6px 0;font-size:14px}
.src{font-size:12px;color:#555}a{color:#243B75}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;
margin:0 0 18px}.summary div{background:#fff;border-radius:10px;padding:10px 12px;
box-shadow:0 1px 3px #0001;font-size:13px}.summary b{display:block;font-size:20px;color:#243B75}
@media print{.scene{break-inside:avoid;box-shadow:none;border:1px solid #ddd}}
"""


def _claim_badges(ids: list[str]) -> str:
    return "".join(f'<a class="claim" href="#claim-{escape(c)}">{escape(c)}</a>' for c in ids)


def _frame(scene: StoryboardScene, shot_index: int = 0, video_src: str | None = None) -> str:
    """Layout sketch of one shot (or the scene's preview clip when rendered)."""
    if video_src:
        return (f'<video class="clip" controls preload="metadata" muted '
                f'src="{escape(video_src)}"></video>')
    shot = scene.shots[min(shot_index, len(scene.shots) - 1)]
    bg_text = scene.background.asset_request or f"library: {scene.background.library_id}"
    color = BEAT_COLORS.get(scene.beat, "#243B75")
    chars = []
    for b in shot.blocking:
        width = max(8.0, min(40.0, 14 * b.scale))
        action = f" · {escape(b.action)}" if b.action else ""
        motion = f" · {escape(b.motion)}" if b.motion != "none" else ""
        z = {"foreground": 3, "midground": 2, "background": 1}[b.depth]
        chars.append(
            f'<div class="char" style="left:{100 * b.x - width / 2:.1f}%;'
            f'top:{max(0.0, 100 * b.y - 30):.1f}%;width:{width:.1f}%;z-index:{z};'
            f'background:{SPEAKER_COLORS.get(b.character, "#ddd")}">{escape(b.character.title())}'
            f"<small>{escape(b.pose)} / {escape(b.expression)}{action}{motion}</small></div>"
        )
    mgs = "".join(f"<span>{escape(m.component)}</span>" for m in scene.motion_graphics)
    return (
        f'<div class="frame" style="background:{color}">'
        f'<div class="bg"><em>{escape(bg_text)}</em></div>'
        f'<div class="mg">{mgs}</div>{"".join(chars)}'
        f'<div class="cam">🎥 {escape(shot.shot_type)} · {escape(shot.angle)} · '
        f'{escape(CAMERA_ICONS.get(shot.camera_move, shot.camera_move))}</div>'
        f'<div class="trans">→ {escape(scene.transition_out.type)} '
        f"{scene.transition_out.duration_s:g}s</div></div>"
    )


def _shots_table(scene: StoryboardScene) -> str:
    rows = []
    for i, sh in enumerate(scene.shots, start=1):
        who = "; ".join(
            f"{escape(b.character)} @({b.x:.2f},{b.y:.2f}) ×{b.scale:g} {escape(b.depth)} "
            f"{escape(b.motion) if b.motion != 'none' else ''}"
            f"{' path→' + str(len(b.path)) if b.path else ''}"
            f"{' enter:' + escape(b.enter) if b.enter != 'none' else ''}"
            for b in sh.blocking) or "–"
        start = escape(sh.starts_at_line or "start")
        rows.append(f"<div class='kv'><b>Shot {i}</b> @ <code>{start}</code>: "
                    f"{escape(sh.shot_type)}, {escape(sh.angle)}, {escape(sh.camera_move)}, "
                    f"focus {escape(sh.focus)}<br><small>{who}</small>"
                    f"{'<br><i>' + escape(sh.note) + '</i>' if sh.note else ''}</div>")
    return "".join(rows)


def _scene(scene: StoryboardScene, script: Script, start_s: float,
           audio: dict[str, tuple[str, float]] | None = None,
           video_src: str | None = None) -> str:
    by_id = {ln.line_id: ln for ln in script.lines}
    audio = audio or {}
    lines = []
    for lid in scene.line_ids:
        ln = by_id.get(lid)
        if ln is None:
            lines.append(f'<li><span class="lid">{escape(lid)}</span><i>missing line</i></li>')
            continue
        direction = f'<span class="dir">({escape(ln.direction)})</span>' if ln.direction else ""
        if lid in audio:
            src, dur = audio[lid]
            timing = f'<span class="est">{dur:g}s (voiced)</span>'
            player = f'<audio class="vo" controls preload="none" src="{escape(src)}"></audio>'
        else:
            timing = f'<span class="est">~{ln.est_duration_s:g}s</span>'
            player = ""
        lines.append(
            f'<li><span class="lid">{escape(lid)}</span>'
            f'<span class="who" style="color:{SPEAKER_COLORS.get(ln.speaker, "#333")}">'
            f"{escape(ln.speaker.upper())}</span>"
            f'<span class="emo">{escape(ln.emotion)}</span>{escape(ln.text)}'
            f"{_claim_badges(ln.claim_ids)} {timing}{direction}{player}</li>"
        )
    mg_rows = []
    for m in scene.motion_graphics:
        ill = '<span class="ill">illustrative · no numbers shown</span>' if m.illustrative else ""
        at = f" @ <code>{escape(m.at_line)}</code>" if m.at_line else ""
        mg_rows.append(
            f'<div class="kv"><b>{escape(m.component)}</b>{at}{ill}{_claim_badges(m.claim_ids)}'
            f"<br><code>{escape(json.dumps(m.props, ensure_ascii=False))}</code></div>"
        )
    sfx = ", ".join(
        f"<code>{escape(fx.id)}</code>" + (f" @ {escape(fx.at_line)}" if fx.at_line else "")
        for fx in scene.sfx
    ) or "–"
    color = BEAT_COLORS.get(scene.beat, "#243B75")
    end_s = start_s + scene.duration_s
    return f"""
<section class="scene" id="{escape(scene.scene_id)}">
  <div class="head"><span class="sid">{escape(scene.scene_id)}</span>
    <span class="badge" style="background:{color}">{escape(scene.beat)}</span>
    <span class="dur">{scene.duration_s:g}s · {_ts(start_s)}–{_ts(end_s)}</span>
    <span class="obj">{escape(scene.objective)}</span></div>
  <div>{_frame(scene, 0, video_src)}
    <h4>Shots ({len(scene.shots)})</h4>{_shots_table(scene)}
    <h4>Background</h4><div class="kv">{escape(scene.background.asset_request or '')}
      {f'library <code>{escape(scene.background.library_id)}</code>'
       if scene.background.library_id else ''}
      · {scene.background.parallax_layers} parallax layers
      · out: {escape(scene.transition_out.type)} {scene.transition_out.duration_s:g}s</div>
  </div>
  <div><h4>Dialogue</h4><ul class="lines">{''.join(lines)}</ul>
    <h4>Motion graphics</h4>{''.join(mg_rows) or '<div class="kv">–</div>'}
    <h4>Sound effects</h4><div class="kv">{sfx}</div>
    <div class="purpose">🎯 {escape(scene.educational_purpose)}</div></div>
</section>"""


def _ts(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def render_storyboard_html(
    board: Storyboard, script: Script, brief: TopicBrief, version: int,
    audio: dict[str, tuple[str, float]] | None = None, preview_src: str | None = None,
    clips: dict[str, str] | None = None,
) -> str:
    """`audio` maps line_id -> (src relative to the HTML file, voiced duration).
    `clips` maps scene_id -> rendered preview clip (relative src); replaces the sketch."""
    clips = clips or {}
    total = board.total_duration_s or 1
    strip = "".join(
        f'<a href="#{escape(s.scene_id)}" title="{escape(s.scene_id)} {escape(s.beat)} '
        f'{s.duration_s:g}s" style="width:{100 * s.duration_s / total:.2f}%;'
        f'background:{BEAT_COLORS.get(s.beat, "#243B75")}">{escape(s.scene_id)}</a>'
        for s in board.scenes
    )
    legend = "".join(f'<span><i class="dot" style="background:{c}"></i>{b}</span>'
                     for b, c in BEAT_COLORS.items())
    scenes, t = [], 0.0
    for s in board.scenes:
        scenes.append(_scene(s, script, t, audio, clips.get(s.scene_id)))
        t += s.duration_s
    if preview_src and preview_src.endswith(".mp4"):
        preview = (f'<div class="kv" style="margin:0 0 18px"><b>🎬 Full episode preview</b>'
                   f'<video controls preload="metadata" style="width:100%;border-radius:12px;'
                   f'margin-top:6px" src="{escape(preview_src)}"></video></div>')
    elif preview_src:
        preview = (f'<div class="kv" style="margin:0 0 18px"><b>🔊 Full voice-over preview</b>'
                   f'<br><audio controls preload="none" style="width:100%" '
                   f'src="{escape(preview_src)}"></audio></div>')
    else:
        preview = ""
    sources = {src.id: src for src in brief.sources}
    claim_items = []
    for c in brief.claims:
        srcs = ", ".join(
            f'<a href="{escape(str(sources[e.source_id].url))}" target="_blank" rel="noopener">'
            f"{escape(sources[e.source_id].publisher)}</a>"
            for e in c.evidence if e.source_id in sources
        )
        note = f" <i>({escape(c.simplification_note)})</i>" if c.simplification_note else ""
        claim_items.append(
            f'<li id="claim-{escape(c.id)}"><b>{escape(c.id)}</b> {escape(c.text)}{note}'
            f'<div class="src">Sources: {srcs}</div></li>'
        )
    graphics = sum(len(s.motion_graphics) for s in board.scenes)
    illustrative = sum(m.illustrative for s in board.scenes for m in s.motion_graphics)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Storyboard · {escape(script.draft.title_working)}</title><style>{CSS}</style></head>
<body><header><h1>{escape(script.draft.title_working)}</h1>
<div class="meta">{escape(brief.central_question)} · storyboard v{version} ·
script v{board.script_version} · {escape(board.rig_version)} · {escape(board.catalogue_version)}
· {board.width}×{board.height} @ {board.fps}fps</div></header>
<main>
<div class="summary"><div><b>{len(board.scenes)}</b>scenes</div>
<div><b>{_ts(board.total_duration_s)}</b>total ({brief.duration.min_s}–{brief.duration.max_s}s
target)</div><div><b>{len(script.lines)}</b>spoken lines</div>
<div><b>{graphics}</b>motion graphics ({illustrative} illustrative)</div></div>
{preview}<div class="timeline">{strip}</div><div class="legend">{legend}</div>
{''.join(scenes)}
<section class="claims"><h3>Verified claims used</h3><ul>{''.join(claim_items)}</ul></section>
</main></body></html>"""
