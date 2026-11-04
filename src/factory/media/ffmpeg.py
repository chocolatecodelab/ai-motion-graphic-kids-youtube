"""Thin FFmpeg/ffprobe wrappers (ported pattern from ai-video-editor-remotion sistem.py)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


class FFmpegError(RuntimeError):
    pass


def _exe(name: str) -> str:
    exe = shutil.which(name)
    if exe is None:
        raise FFmpegError(f"{name} not found on PATH")
    return exe


def run(args: list[str], timeout: int = 1800) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run([_exe("ffmpeg"), "-hide_banner", "-y", *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout,
                          check=False)
    if proc.returncode != 0:
        raise FFmpegError(f"ffmpeg failed ({proc.returncode}): {proc.stderr[-1500:]}")
    return proc


def probe(path: Path) -> dict[str, Any]:
    proc = subprocess.run([_exe("ffprobe"), "-v", "error", "-print_format", "json",
                           "-show_format", "-show_streams", str(path)],
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise FFmpegError(f"ffprobe failed for {path}: {proc.stderr[-500:]}")
    return json.loads(proc.stdout)


def video_info(path: Path) -> dict[str, Any]:
    data = probe(path)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    info: dict[str, Any] = {"duration": float(data["format"].get("duration", 0))}
    if v:
        num, den = (int(x) for x in v.get("r_frame_rate", "0/1").split("/"))
        info.update(width=v["width"], height=v["height"], vcodec=v["codec_name"],
                    fps=num / den if den else 0, pix_fmt=v.get("pix_fmt"),
                    frames=int(v["nb_frames"]) if v.get("nb_frames", "").isdigit() else None)
    if a:
        info.update(acodec=a["codec_name"], sample_rate=int(a.get("sample_rate", 0)))
    return info


def concat(clips: list[Path], out: Path) -> None:
    """Concatenate clips with identical encoding (stream copy, no re-encode)."""
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{c.resolve().as_posix()}'\n" for c in clips),
                       encoding="utf-8")
    run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)])
    listing.unlink(missing_ok=True)


def loudnorm_two_pass(src: Path, dst: Path, integrated: float = -14.0, true_peak: float = -1.0,
                      lra: float = 11.0, sample_rate: int = 48000) -> dict[str, Any]:
    """EBU R128 normalisation (measure, then apply linearly). Returns the measurement."""
    first = run(["-i", str(src), "-af",
                 f"loudnorm=I={integrated}:TP={true_peak}:LRA={lra}:print_format=json",
                 "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", first.stderr, re.S)
    if not m:
        raise FFmpegError("could not read loudnorm measurement")
    meas = json.loads(m.group(0))
    run(["-i", str(src), "-af",
         f"loudnorm=I={integrated}:TP={true_peak}:LRA={lra}:measured_I={meas['input_i']}:"
         f"measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}:"
         f"measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:linear=true",
         "-ar", str(sample_rate), str(dst)])
    return meas


def measure_loudness(path: Path) -> dict[str, float]:
    """Integrated loudness (LUFS) and true peak (dBTP) of a file's audio."""
    proc = run(["-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", proc.stderr)
    tp = re.findall(r"Peak:\s+(-?\d+(?:\.\d+)?) dBFS", proc.stderr)
    return {"integrated_lufs": float(i[-1]) if i else float("nan"),
            "true_peak_dbtp": float(tp[-1]) if tp else float("nan")}
