"""
ffmpeg_wrapper.py — apeluri simple, izolate, catre ffmpeg/ffprobe.
Nu depinde de pachete Python suplimentare (ffmpeg-python etc.) — doar
subprocess, ca sa fie usor de distribuit fara dependinte fragile.
"""

from __future__ import annotations
import json
import shutil
import subprocess


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def find_ffprobe() -> str | None:
    return shutil.which("ffprobe")


def quick_remux(input_path: str, output_path: str) -> tuple[bool, str]:
    """Incearca o remuxare simpla: uneori fisierul are moov valid, dar
    playerul se plange din alte motive (index prost plasat, pts lipsa
    etc.) — asta rezolva acele cazuri, fara reconstructie de la zero."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        return False, "FFmpeg nu a fost gasit in sistem."
    cmd = [
        ffmpeg, "-y",
        "-fflags", "+genpts+igndts",
        "-err_detect", "ignore_err",
        "-i", input_path,
        "-c", "copy",
        "-map", "0",
        "-movflags", "+faststart",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stderr


def probe(path: str) -> dict | None:
    """Ruleaza ffprobe si intoarce informatiile ca dict, sau None daca
    fisierul nu poate fi citit deloc."""
    ffprobe = find_ffprobe()
    if not ffprobe:
        return None
    cmd = [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def validate_output(path: str) -> tuple[bool, str]:
    """Verifica daca fisierul rezultat e intr-adevar redabil: are cel
    putin un stream video, cu durata > 0."""
    info = probe(path)
    if info is None:
        return False, "ffprobe nu a putut citi deloc fisierul rezultat."
    streams = info.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if not video_streams:
        return False, "Niciun stream video detectat in fisierul rezultat."
    fmt = info.get("format", {})
    duration = float(fmt.get("duration", 0) or 0)
    nb_frames = video_streams[0].get("nb_frames")
    if duration <= 0 and not nb_frames:
        return False, "Fisierul rezultat pare sa nu aiba durata/cadre valide."
    return True, f"OK — {video_streams[0].get('codec_name')}, {video_streams[0].get('width')}x{video_streams[0].get('height')}, {nb_frames or '?'} cadre"
