"""Python side of remotion/render-server.mjs: one long-lived Node process renders many
scenes (bundle once, one browser). Protocol: JSON lines on stdin, '@@J {...}' on stdout."""

from __future__ import annotations

import hashlib
import json
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from factory.log import get_logger
from factory.resources import ROOT

log = get_logger(__name__)
REMOTION_DIR = ROOT / "remotion"
PREFIX = "@@J "


def code_hash(remotion_dir: Path = REMOTION_DIR) -> str:
    """Hash of everything that affects rendered pixels (sources, assets, lockfile, server)."""
    h = hashlib.sha256()
    files = sorted(p for p in (remotion_dir / "src").rglob("*") if p.is_file())
    files += sorted(p for p in (remotion_dir / "public").rglob("*") if p.is_file())
    files += [remotion_dir / "package-lock.json", remotion_dir / "render-server.mjs"]
    for p in files:
        if p.exists():
            h.update(p.relative_to(remotion_dir).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


class RenderError(RuntimeError):
    pass


class RemotionRenderer:
    """Context manager: `with RemotionRenderer() as r: r.render("Scene", props, out)`."""

    def __init__(self, remotion_dir: Path = REMOTION_DIR, ready_timeout_s: int = 900,
                 render_timeout_s: int = 3600):
        self.dir = remotion_dir
        self.ready_timeout_s = ready_timeout_s
        self.render_timeout_s = render_timeout_s
        self.proc: subprocess.Popen[str] | None = None
        self._out: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr_tail: list[str] = []
        self._n = 0

    def __enter__(self) -> RemotionRenderer:
        node = shutil.which("node")
        if node is None:
            raise RenderError("node not found on PATH")
        if not (self.dir / "node_modules").exists():
            raise RenderError(f"run `npm install` in {self.dir} first")
        key = code_hash(self.dir)[:16]
        self.proc = subprocess.Popen(
            [node, "render-server.mjs", "--bundle", f".bundle/{key}"], cwd=self.dir,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        msg = self._wait(lambda m: m.get("ready") is True, self.ready_timeout_s)
        log.info("render server ready", bundle=key, startup=msg)
        return self

    def __exit__(self, *exc: object) -> None:
        if self.proc is None:
            return
        try:
            if self.proc.stdin:
                self.proc.stdin.close()
            self.proc.wait(timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()
        self.proc = None

    def _read_stdout(self) -> None:
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            if line.startswith(PREFIX):
                try:
                    self._out.put(json.loads(line[len(PREFIX):]))
                except json.JSONDecodeError:
                    pass
        self._out.put({"eof": True})

    def _read_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        for line in self.proc.stderr:
            self._stderr_tail = (self._stderr_tail + [line.rstrip()])[-40:]

    def _wait(self, match: Any, timeout_s: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RenderError(f"render server timeout after {timeout_s}s; stderr: "
                                  + " | ".join(self._stderr_tail[-8:]))
            try:
                msg = self._out.get(timeout=min(remaining, 5))
            except queue.Empty:
                continue
            if msg.get("eof"):
                raise RenderError("render server exited; stderr: "
                                  + " | ".join(self._stderr_tail[-12:]))
            if match(msg):
                return msg

    def render(self, composition: str, props: dict[str, Any], out: Path, scale: float = 1.0,
               crf: int = 20) -> int:
        """Render to `out` (mp4, muted). Returns elapsed milliseconds."""
        assert self.proc and self.proc.stdin, "use as a context manager"
        self._n += 1
        req_id = f"r{self._n}"
        req = {"id": req_id, "composition": composition, "props": props,
               "out": str(out.resolve()), "scale": scale, "crf": crf}
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        msg = self._wait(lambda m: m.get("id") == req_id, self.render_timeout_s)
        if not msg.get("ok"):
            raise RenderError(f"render failed: {str(msg.get('error'))[:1500]}")
        return int(msg.get("ms", 0))
