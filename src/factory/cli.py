"""`factory` command-line interface."""

from __future__ import annotations

import getpass
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from factory import __version__
from factory.config import get_settings
from factory.db.models import Episode, Lane, ModelUsage, ProductionJob
from factory.db.session import session_scope
from factory.doctor import Status, run_all
from factory.log import configure_logging

app = typer.Typer(help="AI Kids Educational Animation Factory", no_args_is_help=True)
console = Console()

_STYLE = {Status.OK: "green", Status.WARN: "yellow", Status.FAIL: "red"}
_JOB_STYLE = {"succeeded": "green", "awaiting_approval": "cyan", "running": "yellow",
              "queued": "white", "pending": "dim", "failed_retryable": "yellow",
              "failed_permanent": "red", "cancelled": "dim"}
DEFAULT_PILOT = Path("config/pilots/why-is-the-sky-blue.yaml")


def _workflow():  # type: ignore[no-untyped-def]
    from factory.providers.llm import get_llm
    from factory.workflow import build_workflow

    return build_workflow(get_llm(get_settings(), session_scope))


@app.callback()
def _main() -> None:
    configure_logging(get_settings().log_level)


@app.command()
def version() -> None:
    """Print the factory version."""
    console.print(__version__)


@app.command()
def doctor() -> None:
    """Check tools, services and configuration. Exits 1 if any check fails."""
    results = run_all(get_settings())
    table = Table(title="factory doctor")
    table.add_column("check")
    table.add_column("status")
    table.add_column("detail", overflow="fold")
    for r in results:
        table.add_row(r.name, f"[{_STYLE[r.status]}]{r.status.value}[/]", r.detail)
    console.print(table)
    if any(r.status is Status.FAIL for r in results):
        raise typer.Exit(code=1)


@app.command()
def pilot(brief: Path = typer.Argument(DEFAULT_PILOT, exists=True, dir_okay=False)) -> None:
    """Create an episode from a hand-written brief and queue its stages."""
    from factory.services import create_episode_from_brief

    with session_scope() as s:
        try:
            ep = create_episode_from_brief(s, brief, get_settings(), _workflow())
        except ValueError as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(1) from exc
        console.print(f"Created episode [bold]{ep.slug}[/] ({ep.id}). "
                      f"Run: [cyan]uv run factory worker --lane llm[/]")


@app.command("run-episode")
def run_episode(
    brief: Path = typer.Argument(DEFAULT_PILOT, exists=True, dir_okay=False),
    episode: str = typer.Option(None, help="Continue an existing episode instead of creating one"),
) -> None:
    """One command: create the episode (or continue it) and run every lane until it is done
    or waiting for the owner's approval."""
    from factory.pipeline.runner import Worker
    from factory.services import create_episode_from_brief, find_episode

    workflow = _workflow()
    with session_scope() as s:
        if episode:
            ep = find_episode(s, episode)
        else:
            try:
                ep = create_episode_from_brief(s, brief, get_settings(), workflow)
            except ValueError as exc:
                console.print(f"[red]{exc}[/] (use --episode to continue it)")
                raise typer.Exit(1) from exc
        slug, ep_id = ep.slug, ep.id
    console.print(f"episode [bold]{slug}[/]")
    workers = [Worker(ln, workflow, session_scope, get_settings())
               for ln in (Lane.LLM, Lane.MEDIA, Lane.RENDER)]
    did_work = True
    while did_work:
        did_work = False
        for w in workers:
            for o in w.run_until_idle():
                did_work = True
                style = _JOB_STYLE.get(o.status.value, "white")
                console.print(f"  [{w.lane.value}] {o.stage}: [{style}]{o.status.value}[/]")
    with session_scope() as s:
        jobs = s.scalars(select(ProductionJob).where(ProductionJob.episode_id == ep_id)).all()
        waiting = [j.stage for j in jobs if j.status.value == "awaiting_approval"]
        failed = [j for j in jobs if j.status.value in ("failed_permanent", "failed_retryable")]
        ep_status = s.get(Episode, ep_id).status.value  # type: ignore[union-attr]
    if waiting:
        console.print(f"[cyan]Waiting for your approval:[/] {', '.join(waiting)} → review, then "
                      f"`factory approve {slug} {waiting[0]}` and run "
                      f"`factory run-episode --episode {slug}` again.")
    for j in failed:
        console.print(f"[red]{j.stage} {j.status.value}:[/] {(j.error_message or '')[:300]}")
    console.print(f"episode status: [bold]{ep_status}[/]")


@app.command()
def worker(
    lane: Lane = typer.Option(Lane.LLM, help="Which lane to process"),
    all_lanes: bool = typer.Option(False, "--all-lanes",
                                   help="Process llm + media + render lanes until idle"),
    loop: bool = typer.Option(False, help="Keep polling instead of exiting when idle"),
    poll_s: int = typer.Option(15, help="Seconds between polls in --loop mode"),
) -> None:
    """Process queued jobs for one lane (or all local lanes)."""
    from factory.pipeline.runner import Worker

    workflow = _workflow()
    lanes = [Lane.LLM, Lane.MEDIA, Lane.RENDER] if all_lanes else [lane]
    workers = [Worker(ln, workflow, session_scope, get_settings()) for ln in lanes]
    console.print("workers started: " + ", ".join(w.worker_id for w in workers))
    try:
        while True:
            did_work = True
            while did_work:  # alternate lanes: finishing one lane can unblock another
                did_work = False
                for w in workers:
                    for o in w.run_until_idle():
                        did_work = True
                        style = _JOB_STYLE.get(o.status.value, "white")
                        hit = " (cache hit)" if o.cache_hit else ""
                        console.print(f"  [{w.lane.value}] {o.stage}: "
                                      f"[{style}]{o.status.value}[/]{hit}")
            if not loop:
                break
            time.sleep(poll_s)
    except KeyboardInterrupt:
        console.print("stopped")


@app.command()
def status(episode: str = typer.Argument(None, help="Episode slug, number or id")) -> None:
    """List episodes, or show the jobs of one episode."""
    from factory.services import find_episode

    with session_scope() as s:
        if episode is None:
            table = Table(title="episodes")
            for col in ("#", "slug", "status", "created"):
                table.add_column(col)
            for ep in s.scalars(select(Episode).order_by(Episode.created_at)):
                table.add_row(str(ep.number), ep.slug, ep.status.value,
                              f"{ep.created_at:%Y-%m-%d %H:%M}")
            console.print(table)
            return
        ep = find_episode(s, episode)
        jobs = s.scalars(select(ProductionJob).where(ProductionJob.episode_id == ep.id)
                         .order_by(ProductionJob.created_at)).all()
        usage = s.scalars(select(ModelUsage).where(ModelUsage.episode_id == ep.id)).all()
        table = Table(title=f"{ep.slug} · {ep.status.value}")
        for col in ("stage", "status", "attempt", "output / error"):
            table.add_column(col, overflow="fold")
        for j in jobs:
            detail = j.error_message or ", ".join(
                f"{k}={v}" for k, v in (j.output_refs or {}).items() if k not in ("sha256",))
            style = _JOB_STYLE.get(j.status.value, "white")
            table.add_row(j.stage, f"[{style}]{j.status.value}[/]", str(j.attempt), detail[:300])
        console.print(table)
        if usage:
            per: dict[str, list[float]] = {}
            for u in usage:
                agent = str((u.units or {}).get("agent", "other"))
                row = per.setdefault(agent, [0, 0, 0.0])
                row[0] += 1
                row[1] += int((u.units or {}).get("output_tokens", 0))
                row[2] += float(u.cost_usd)
            cost_table = Table(title="usage per stage (claude -p, subscription: not billed)")
            for col in ("stage", "calls", "output tokens", "equiv. API $"):
                cost_table.add_column(col)
            for agent, (calls, toks, cost) in sorted(per.items()):
                cost_table.add_row(agent, str(int(calls)), str(int(toks)), f"{cost:.2f}")
            total = [sum(r[i] for r in per.values()) for i in range(3)]
            cost_table.add_row("[bold]total[/]", str(int(total[0])), str(int(total[1])),
                               f"{total[2]:.2f}")
            console.print(cost_table)


@app.command()
def approve(
    episode: str,
    stage: str = typer.Argument("script_validate"),
    notes: str = typer.Option(None, help="Optional reviewer notes"),
    by: str = typer.Option(None, help="Reviewer name (default: OS user)"),
) -> None:
    """Approve a stage that is awaiting approval (default: the script)."""
    from factory.services import approve_stage, find_episode

    with session_scope() as s:
        ep = find_episode(s, episode)
        try:
            approve_stage(s, ep, stage, _workflow(), by or getpass.getuser(), notes)
        except ValueError as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(1) from exc
    console.print(f"Approved {stage} for {ep.slug}.")


@app.command()
def retry(episode: str, stage: str) -> None:
    """Re-run one stage; downstream stages re-run after it, upstream results are reused."""
    from factory.pipeline import queue
    from factory.services import find_episode

    with session_scope() as s:
        ep = find_episode(s, episode)
        try:
            queue.retry_stage(s, ep.id, stage, _workflow())
        except ValueError as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(1) from exc
    console.print(f"Queued {stage} for {ep.slug}.")


@app.command()
def sync(episode: str) -> None:
    """Add jobs for workflow stages added after this episode was created."""
    from factory.pipeline import queue
    from factory.services import find_episode

    with session_scope() as s:
        ep = find_episode(s, episode)
        added = queue.sync_episode_jobs(s, ep.id, _workflow())
        names = ", ".join(f"{j.stage} ({j.status.value})" for j in added) or "nothing to add"
    console.print(f"{ep.slug}: {names}")


@app.command()
def cancel(episode: str) -> None:
    """Cancel all active jobs of an episode."""
    from factory.pipeline import queue
    from factory.services import find_episode

    with session_scope() as s:
        ep = find_episode(s, episode)
        n = queue.cancel_episode(s, ep.id)
    console.print(f"Cancelled {n} job(s) for {ep.slug}.")


@app.command("storyboard-html")
def storyboard_html(episode: str) -> None:
    """(Re)build the HTML review page for an episode's current storyboard."""
    from factory import artifacts
    from factory.db.models import JobStatus
    from factory.pipeline import queue
    from factory.schemas.brief import TopicBrief
    from factory.schemas.renderplan import RenderPlan
    from factory.schemas.script import Script
    from factory.schemas.storyboard import Storyboard
    from factory.services import find_episode
    from factory.storyboard_html import render_storyboard_html

    content = Path(get_settings().content_dir)
    with session_scope() as s:
        ep = find_episode(s, episode)
        try:
            refs = queue.upstream_outputs(s, ep.id, ("brief", "script", "storyboard"))
        except ValueError as exc:
            console.print(f"[red]{exc}[/] (storyboard must have {JobStatus.SUCCEEDED.value})")
            raise typer.Exit(1) from exc
        def optional(stage: str) -> dict | None:  # type: ignore[type-arg]
            try:
                return queue.upstream_outputs(s, ep.id, (stage,))[stage]
            except ValueError:
                return None

        voice_ref = optional("voice")
        render_ref = optional("render_scenes")
        assemble_ref = optional("assemble")
        timing_ref = optional("timing")
    board = artifacts.read_model(content, refs["storyboard"], Storyboard)
    script = artifacts.read_model(content, refs["script"], Script)
    brief = artifacts.read_model(content, refs["brief"], TopicBrief)
    version = int(refs["storyboard"]["version"])
    out = content / Path(refs["storyboard"]["path"]).with_suffix(".html")

    import os

    def rel(p: str) -> str:
        return Path(os.path.relpath(content / p, out.parent)).as_posix()

    audio, preview, clips = None, None, None
    if voice_ref is not None:
        from factory.schemas.voice import VoiceManifest

        manifest = artifacts.read_model(content, voice_ref, VoiceManifest)
        if manifest.script_version == script.version:
            audio = {v.line_id: (rel(v.file), v.duration_s) for v in manifest.lines}
            preview = rel(manifest.preview_file)
        else:
            console.print("[yellow]voice is from an older script version; not embedded[/]")
    plan_matches = (timing_ref is not None and render_ref is not None
                    and artifacts.read_model(content, timing_ref, RenderPlan).storyboard_version
                    == version)
    if plan_matches and render_ref is not None:
        clips = {c["scene_id"]: rel(c["file"]) for c in render_ref["clips"]}
    if assemble_ref is not None and plan_matches:
        preview = rel(assemble_ref["video"])
    out.write_text(render_storyboard_html(board, script, brief, version, audio, preview, clips),
                   encoding="utf-8")
    extras = [x for x, ok in (("voice-over", audio), ("scene clips", clips)) if ok]
    console.print(f"wrote {out}" + (f" (with {', '.join(extras)})" if extras else ""))


@app.command()
def schemas(out_dir: Path = typer.Option(Path("schemas"))) -> None:
    """Export JSON Schemas for all stage artifacts (shared with Remotion)."""
    from factory.schemas import export_json_schemas

    for p in export_json_schemas(out_dir):
        console.print(f"wrote {p}")


if __name__ == "__main__":
    app()
