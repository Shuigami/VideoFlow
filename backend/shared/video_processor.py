"""Pipeline FFmpeg : analyse, transcodage et miniature."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

_NOISE_PATTERNS = (
    re.compile(r"^ffmpeg version"),
    re.compile(r"^Copyright"),
    re.compile(r"^\s+built with"),
    re.compile(r"^\s+configuration:"),
    re.compile(r"^\s+lib"),
)


def _resolve_binary(name: str) -> str:
    candidates = [
        os.environ.get(f"{name.upper()}_PATH"),
        f"/opt/bin/{name}",
        str(Path(__file__).resolve().parent / name),
        shutil.which(name),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
        if candidate and shutil.which(candidate):
            return candidate
    raise FileNotFoundError(
        f"{name} introuvable. Installez FFmpeg ou configurez {name.upper()}_PATH."
    )


def _format_ffmpeg_error(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    relevant = [
        line
        for line in lines
        if not any(pattern.search(line) for pattern in _NOISE_PATTERNS)
    ]
    if not relevant:
        return "Erreur FFmpeg inconnue."
    return "\n".join(relevant[-8:])


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(_format_ffmpeg_error(result.stderr))
    return result


def probe_video(source: Path) -> dict[str, Any]:
    ffprobe = _resolve_binary("ffprobe")
    output = run_command(
        [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(source),
        ]
    )
    payload = json.loads(output.stdout)
    video_stream = next(
        (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"),
        {},
    )
    duration = float(payload.get("format", {}).get("duration") or video_stream.get("duration") or 0)
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)

    return {
        "duration": round(duration, 2),
        "width": width,
        "height": height,
        "codec": video_stream.get("codec_name", "unknown"),
        "sizeBytes": int(payload.get("format", {}).get("size") or source.stat().st_size),
    }


def _thumbnail_command(
    ffmpeg: str,
    source: Path,
    destination: Path,
    seek: str | None,
) -> list[str]:
    args = [ffmpeg, "-y", "-fflags", "+genpts", "-i", str(source)]
    if seek is not None:
        args.extend(["-ss", seek])
    args.extend(
        [
            "-frames:v",
            "1",
            "-update",
            "1",  # requis par FFmpeg 6+ pour écrire une seule image
            "-q:v",
            "2",
            str(destination),
        ]
    )
    return args


def generate_thumbnail(source: Path, destination: Path) -> None:
    ffmpeg = _resolve_binary("ffmpeg")
    destination.parent.mkdir(parents=True, exist_ok=True)

    attempts = ["00:00:01", "00:00:00", None]
    last_error: Exception | None = None

    for seek in attempts:
        try:
            if destination.exists():
                destination.unlink()
            run_command(_thumbnail_command(ffmpeg, source, destination, seek))
            if destination.exists() and destination.stat().st_size > 0:
                return
        except RuntimeError as exc:
            last_error = exc

    raise RuntimeError(
        last_error.args[0] if last_error else "Impossible de générer la miniature."
    )


# Hauteurs cibles du transcodage adaptatif (du plus bas au plus haut)
TRANSCODE_HEIGHTS = (144, 360, 480, 720, 1080)


def transcode(source: Path, destination: Path, target_height: int) -> None:
    ffmpeg = _resolve_binary("ffmpeg")
    destination.parent.mkdir(parents=True, exist_ok=True)
    scale = f"-2:{target_height}"
    audio_bitrate = "64k" if target_height <= 360 else "128k"
    run_command(
        [
            ffmpeg,
            "-y",
            "-fflags",
            "+genpts",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-vf",
            f"scale={scale}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
            "-movflags",
            "+faststart",
            "-max_muxing_queue_size",
            "1024",
            str(destination),
        ]
    )


def process_video(source: Path, work_dir: Path) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    metadata = probe_video(source)

    thumbnail_path = work_dir / "thumbnail.jpg"
    generate_thumbnail(source, thumbnail_path)

    outputs: dict[str, Path] = {}
    source_height = metadata.get("height") or 0

    for height in TRANSCODE_HEIGHTS:
        if source_height and source_height < height - 50:
            continue
        label = f"{height}p"
        output_path = work_dir / f"{label}.mp4"
        transcode(source, output_path, height)
        outputs[label] = output_path

    if not outputs:
        fallback_height = min(source_height, 144) if source_height else 144
        fallback = work_dir / "source-normalized.mp4"
        transcode(source, fallback, fallback_height)
        outputs["source"] = fallback

    return {
        "metadata": metadata,
        "outputs": outputs,
        "thumbnail": thumbnail_path,
    }
