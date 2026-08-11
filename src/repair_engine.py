"""
repair_engine.py — orchestreaza procesul de reparare complet.

Strategie:
  1. Incearca intai o remuxare rapida (ffmpeg -c copy) — rezolva cazurile
     usoare, unde moov exista dar ceva minor e in neregula.
  2. Daca esueaza sau fisierul rezultat tot nu e valid, trece la
     reparare bazata pe fisier de referinta:
       a. parseaza track-ul video din REFERINTA (codec, dimensiuni, etc.)
       b. localizeaza / presupune mdat-ul in fisierul corupt
       c. scaneaza esantioanele reale din acel mdat
       d. construieste un moov nou, folosind sablonul din referinta +
          esantioanele reale
       e. scrie fisierul de iesire: ftyp + moov (nou) + mdat (copiat)
"""

from __future__ import annotations
import os
import struct
from dataclasses import dataclass

import mp4_boxes
import moov_parser
import moov_builder
import sample_scanner
import ffmpeg_wrapper
import audio_recovery


@dataclass
class RepairResult:
    success: bool
    method_used: str      # "quick_remux" sau "reference_rebuild" sau "failed"
    message: str
    output_path: str | None = None


def _find_mdat_or_treat_whole_as_mdat(path: str) -> tuple[int, int]:
    """Incearca sa gaseasca boxul mdat in fisierul corupt. Daca nu
    gaseste NICIUN box valid de la inceput (fisier complet fara
    structura, doar date brute), trateaza tot fisierul ca fiind
    echivalentul continutului unui mdat.

    Intoarce (payload_start, payload_size) absolut in fisier."""
    try:
        boxes = mp4_boxes.parse_file(path)
    except Exception:
        boxes = []

    mdat = next((b for b in boxes if b.box_type == "mdat"), None)
    if mdat is not None:
        file_size = os.path.getsize(path)
        # daca boxul e trunchiat (size-ul declarat depaseste ce a mai
        # ramas cu adevarat in fisier), folosim ce chiar exista
        actual_payload_size = min(mdat.payload_size, file_size - mdat.payload_start)
        return mdat.payload_start, actual_payload_size

    # niciun mdat gasit explicit — posibil fisierul nu are deloc atomi
    # recognoscibili la inceput (rar, dar tratam defensiv): incercam sa
    # gasim manual semnatura "mdat" oriunde in primii cativa KB
    with open(path, "rb") as f:
        head = f.read(65536)
    idx = head.find(b"mdat")
    if idx >= 4:
        payload_start = idx + 4
        file_size = os.path.getsize(path)
        return payload_start, file_size - payload_start

    # chiar nimic recognoscibil - tratam tot fisierul ca date brute
    file_size = os.path.getsize(path)
    return 0, file_size


def _get_ftyp_bytes(path: str) -> bytes:
    """Incearca sa extraga boxul ftyp existent din fisierul corupt (daca
    exista); altfel foloseste un ftyp minimal, generic, compatibil cu
    marea majoritate a playerelor."""
    try:
        boxes = mp4_boxes.parse_file(path)
        ftyp = next((b for b in boxes if b.box_type == "ftyp"), None)
        if ftyp is not None:
            with open(path, "rb") as f:
                f.seek(ftyp.start)
                return f.read(ftyp.total_size)
    except Exception:
        pass
    # ftyp minimal generic (major brand "isom", compatibil larg)
    payload = b"isom" + struct.pack(">I", 512) + b"isomiso2avc1mp41"
    size = 8 + len(payload)
    return struct.pack(">I4s", size, b"ftyp") + payload


def repair_with_reference(corrupt_path: str, reference_path: str, output_path: str) -> RepairResult:
    ref_boxes = mp4_boxes.parse_file(reference_path)
    ref_tracks = moov_parser.parse_all_tracks(reference_path, ref_boxes)
    ref_video_track = next((t for t in ref_tracks if t.handler_type == "vide"), None)
    if ref_video_track is None:
        return RepairResult(False, "failed", "Fisierul de referinta nu are un track video valid — verifica ca e un fisier sanatos, redabil.")
    if not ref_video_track.sample_table.codec_config_raw:
        return RepairResult(False, "failed", "Nu am putut extrage configuratia codec-ului (avcC/hvcC) din fisierul de referinta.")

    ref_trak_boxes = ref_boxes[0].find_all("trak") if False else \
        next(b for b in ref_boxes if b.box_type == "moov").find_all("trak")
    ref_audio = None
    for trak in ref_trak_boxes:
        candidate = audio_recovery.parse_audio_track(reference_path, trak)
        if candidate is not None:
            ref_audio = candidate
            break

    audio_note = "Fisierul de referinta nu are track audio."
    if ref_audio:
        verdict = audio_recovery.classify_audio_recoverability(ref_audio)
        audio_note = verdict.reason    
    is_hevc = ref_video_track.sample_table.codec_fourcc in ("hvc1", "hev1")

    mdat_payload_start, mdat_payload_size = _find_mdat_or_treat_whole_as_mdat(corrupt_path)
    with open(corrupt_path, "rb") as f:
        f.seek(mdat_payload_start)
        mdat_data = f.read(mdat_payload_size)

    if len(mdat_data) < 1024:
        return RepairResult(False, "failed", "Fisierul corupt pare sa nu contina deloc date video utilizabile (prea mic).")

    scanned = sample_scanner.scan_length_prefixed_samples(mdat_data, is_hevc=is_hevc)
    if len(scanned) < 2:
        return RepairResult(False, "failed",
                             "Nu am reusit sa identific esantioane video valide in fisierul corupt. "
                             "E posibil ca datele sa fie corupte si la nivel de continut, nu doar in header.")

    ftyp_bytes = _get_ftyp_bytes(corrupt_path)

    # pasul 1: construim moov cu offset placeholder=0, doar ca sa aflam
    # dimensiunea lui exacta (fixa, indiferent de valorile reale din co64)
    moov_pass1 = moov_builder.build_moov_video_only(ref_video_track, scanned, mdat_payload_start_placeholder=0)
    real_mdat_start = len(ftyp_bytes) + len(moov_pass1) + 8  # +8 = header-ul boxului mdat nou

    # pasul 2: reconstruim moov cu offset-urile reale
    moov_final = moov_builder.build_moov_video_only(ref_video_track, scanned, mdat_payload_start_placeholder=real_mdat_start)

    mdat_header = struct.pack(">I4s", 8 + len(mdat_data), b"mdat")

    with open(output_path, "wb") as out:
        out.write(ftyp_bytes)
        out.write(moov_final)
        out.write(mdat_header)
        out.write(mdat_data)

    ok, msg = ffmpeg_wrapper.validate_output(output_path)
    if ok:
        return RepairResult(True, "reference_rebuild",
                              f"Reparat cu succes folosind fisierul de referinta ({len(scanned)} cadre reconstruite). "
                             f"{msg} | Audio: {audio_note}",
                             output_path)
    return RepairResult(False, "reference_rebuild",
                         f"Fisierul a fost reconstruit dar validarea a esuat: {msg}. "
                         "Verifica manual daca se poate reda macar partial.",
                         output_path)


def repair(corrupt_path: str, reference_path: str, output_path: str,
           progress_callback=None) -> RepairResult:
    def report(msg: str):
        if progress_callback:
            progress_callback(msg)

    report("Incerc mai intai o remuxare rapida...")
    quick_ok, quick_err = ffmpeg_wrapper.quick_remux(corrupt_path, output_path)
    if quick_ok:
        valid, msg = ffmpeg_wrapper.validate_output(output_path)
        if valid:
            return RepairResult(True, "quick_remux", f"Reparat cu o remuxare simpla, fara sa fie nevoie de fisierul de referinta. {msg}", output_path)

    report("Remuxarea rapida nu a fost suficienta — trec la reconstructie folosind fisierul de referinta...")
    if not reference_path or not os.path.isfile(reference_path):
        return RepairResult(False, "failed",
                             "Remuxarea rapida a esuat si nu ai furnizat un fisier de referinta valid pentru reconstructie avansata.")

    return repair_with_reference(corrupt_path, reference_path, output_path)
