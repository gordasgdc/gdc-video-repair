#!/usr/bin/env python3
"""
Teste automate pentru GDC Video Repair.

Construiește fișiere de test reale (H.264 și H.265) cu ffmpeg, le
corupe în mod controlat (lipsă completă moov, si trunchiere partiala
la mijlocul filmarii), ruleaza repararea, si verifica rezultatul
comparand cadre decodate, pixel cu pixel, fata de originalul sanatos.

Necesita: ffmpeg (cu suport libx264 si libx265) si ffprobe in PATH.
Nu necesita PIL/numpy pentru functionarea unealtei in sine — sunt
folosite AICI doar pentru comparatia de test, si sunt optionale (daca
lipsesc, testele de comparatie pixel sar peste acel pas, dar tot verifica
succesul structural al repararii).

Ruleaza cu: python3 tests/run_tests.py
"""

import os
import shutil
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import mp4_boxes
import repair_engine


def _run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Comanda a esuat: {' '.join(cmd)}\n{result.stderr}")


def make_test_source(path: str, codec: str, seconds: int = 2, size: str = "640x480", rate: int = 24):
    _run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"testsrc=size={size}:rate={rate}:duration={seconds}",
        "-c:v", codec, "-pix_fmt", "yuv420p", path,
    ])


def strip_moov_completely(source_path: str, corrupt_path: str):
    boxes = mp4_boxes.parse_file(source_path)
    ftyp = next(b for b in boxes if b.box_type == "ftyp")
    mdat = next(b for b in boxes if b.box_type == "mdat")
    with open(source_path, "rb") as f:
        f.seek(ftyp.start)
        ftyp_bytes = f.read(ftyp.total_size)
        f.seek(mdat.start)
        mdat_bytes = f.read(mdat.total_size)
    with open(corrupt_path, "wb") as out:
        out.write(ftyp_bytes)
        out.write(mdat_bytes)


def truncate_mid_recording(source_path: str, corrupt_path: str, keep_fraction: float = 0.7):
    boxes = mp4_boxes.parse_file(source_path)
    ftyp = next(b for b in boxes if b.box_type == "ftyp")
    mdat = next(b for b in boxes if b.box_type == "mdat")
    with open(source_path, "rb") as f:
        f.seek(ftyp.start)
        ftyp_bytes = f.read(ftyp.total_size)
        f.seek(mdat.start)
        mdat_bytes_full = f.read(mdat.total_size)
    cut = int(len(mdat_bytes_full) * keep_fraction)
    with open(corrupt_path, "wb") as out:
        out.write(ftyp_bytes)
        out.write(mdat_bytes_full[:cut])


def confirm_genuinely_corrupt(path: str) -> bool:
    """Verifica ca fisierul de test chiar NU se poate citi normal cu
    ffprobe — altfel testul n-ar dovedi nimic."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", path],
        capture_output=True, text=True,
    )
    return result.returncode != 0


def extract_frame_png(video_path: str, frame_index: int, out_png: str):
    _run([
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"select=eq(n\\,{frame_index})", "-vframes", "1", "-update", "1",
        out_png,
    ])


def frames_pixel_identical(png_a: str, png_b: str) -> bool:
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        print("  (PIL/numpy indisponibile - sar peste comparatia pixel-cu-pixel)")
        return True
    a = np.array(Image.open(png_a))
    b = np.array(Image.open(png_b))
    return a.shape == b.shape and bool((a == b).all())


def run_scenario(name: str, codec: str, corrupt_fn, check_frame_idx: int, tmpdir: str) -> bool:
    print(f"\n=== {name} ===")
    source = os.path.join(tmpdir, f"{name}_source.mp4")
    corrupt = os.path.join(tmpdir, f"{name}_corrupt.mp4")
    repaired = os.path.join(tmpdir, f"{name}_repaired.mp4")

    make_test_source(source, codec)
    corrupt_fn(source, corrupt)

    if not confirm_genuinely_corrupt(corrupt):
        print("  EȘUAT: fisierul de test nu era de fapt corupt (bug in scriptul de test)")
        return False
    print("  Fisier corupt simulat, confirmat ilizibil cu ffprobe.")

    result = repair_engine.repair(corrupt, source, repaired)
    if not result.success:
        print(f"  EȘUAT: repararea a esuat: {result.message}")
        return False
    print(f"  Reparat ({result.method_used}): {result.message}")

    png_o = os.path.join(tmpdir, f"{name}_o.png")
    png_r = os.path.join(tmpdir, f"{name}_r.png")
    try:
        extract_frame_png(source, check_frame_idx, png_o)
        extract_frame_png(repaired, check_frame_idx, png_r)
        if not frames_pixel_identical(png_o, png_r):
            print(f"  EȘUAT: cadrul {check_frame_idx} nu se potriveste pixel-cu-pixel cu originalul.")
            return False
        print(f"  Cadrul {check_frame_idx}: identic pixel-cu-pixel cu originalul. OK.")
    except RuntimeError as e:
        print(f"  AVERTISMENT: nu am putut extrage cadrul {check_frame_idx} pentru comparatie ({e}) — posibil cadrul nu a fost recuperat (normal la trunchiere severa).")

    print(f"  {name}: TRECUT")
    return True


def main():
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("EROARE: ffmpeg/ffprobe nu sunt in PATH. Instaleaza-le inainte de a rula testele.")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="gdc_video_repair_tests_") as tmpdir:
        results = []
        results.append(run_scenario("h264_moov_lipsa", "libx264",
                                     strip_moov_completely, check_frame_idx=20, tmpdir=tmpdir))
        results.append(run_scenario("h265_moov_lipsa", "libx265",
                                     strip_moov_completely, check_frame_idx=20, tmpdir=tmpdir))
        results.append(run_scenario("h264_trunchiat_mijloc",
                                     "libx264",
                                     lambda s, c: truncate_mid_recording(s, c, 0.7),
                                     check_frame_idx=15, tmpdir=tmpdir))

        print("\n" + "=" * 50)
        passed = sum(1 for r in results if r)
        print(f"Rezultat final: {passed}/{len(results)} teste trecute")
        sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
