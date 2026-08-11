"""
codec_support.py — extinde mp4_boxes.py / moov_parser.py pentru codecuri
in afara de H.264/H.265.

Diferenta cheie fata de H.264/H.265: ProRes, DNxHD/DNxHR si MPEG-2 NU
folosesc NAL-uri length-prefixed in interiorul esantioanelor — fiecare
esantion e deja un bloc opac (un cadru complet ProRes/DNx, sau o secventa
MPEG-2 GOP-based). Asta schimba sample_scanner.py: nu mai poti parcurge
octet-cu-octet cautand tipuri de NAL, dar in schimb fiecare din aceste
codecuri are propriul "magic marker" la inceputul fiecarui cadru, pe care
il putem cauta direct in mdat.
"""

from __future__ import annotations
import struct


# fourCC-uri stsd -> (nume afisat, marker de inceput de cadru in bytes, la ce offset)
KNOWN_VIDEO_CODECS = {
    # H.264 / H.265 — deja suportate, length-prefixed, fara marker fix
    "avc1": ("H.264", None, 0),
    "avc3": ("H.264", None, 0),
    "hvc1": ("H.265/HEVC", None, 0),
    "hev1": ("H.265/HEVC", None, 0),

    # ProRes — fiecare frame incepe cu "icpf" la offset 4 in interiorul
    # frame-ului (dupa un header de 4 octeti cu frame size)
    "apco": ("Apple ProRes 422 Proxy", b"icpf", 4),
    "apcs": ("Apple ProRes 422 LT", b"icpf", 4),
    "apcn": ("Apple ProRes 422", b"icpf", 4),
    "apch": ("Apple ProRes 422 HQ", b"icpf", 4),
    "ap4h": ("Apple ProRes 4444", b"icpf", 4),
    "ap4x": ("Apple ProRes 4444 XQ", b"icpf", 4),

    # DNxHD / DNxHR — fiecare frame incepe cu signature-ul fix
    # 0x00 0x00 0x02 0x80 0x01 (definit in specificatia SMPTE VC-3)
    "AVdn": ("Avid DNxHD", b"\x00\x00\x02\x80\x01", 0),
    "AVdh": ("Avid DNxHR", b"\x00\x00\x02\x80\x01", 0),

    # MPEG-2 — fiecare frame/picture incepe cu un start code 0x000001 00
    "mp2v": ("MPEG-2 Video", b"\x00\x00\x01\x00", 0),
}


def detect_codec_from_stsd_fourcc(fourcc: str) -> tuple[str, bytes | None, int]:
    """Intoarce (nume_afisat, marker_frame_start, offset_marker) pentru
    un fourCC citit din stsd. Daca fourCC-ul e necunoscut, il trateaza
    ca 'generic' — reconstructia doar-video-only nu va fi posibila
    fara marker, dar remuxarea rapida (ffmpeg -c copy) tot poate merge
    daca moov-ul original mai exista partial."""
    return KNOWN_VIDEO_CODECS.get(fourcc, (fourcc, None, 0))


def scan_marker_based_samples(data: bytes, marker: bytes, marker_offset: int,
                               max_samples: int = 500_000) -> list[tuple[int, int]]:
    """Pentru codecuri intraframe cu marker fix (ProRes, DNxHD, MPEG-2):
    gaseste toate poziliile unde apare marker-ul, calculeaza dimensiunea
    fiecarui cadru ca distanta pana la urmatorul marker gasit.

    Spre deosebire de H.264/H.265, aceste codecuri sunt aproape mereu
    INTRAFRAME (fiecare cadru e complet independent, fara P/B-frames),
    ceea ce simplifica mult reconstructia — nu mai ai nevoie sa
    identifici keyframe-uri separat, orice cadru e keyframe.

    Intoarce lista de (offset, size), unde offset e inceputul REAL al
    cadrului (inainte de marker, tinand cont de marker_offset)."""
    positions = []
    search_from = 0
    n = len(data)
    while len(positions) < max_samples:
        idx = data.find(marker, search_from)
        if idx == -1:
            break
        frame_start = idx - marker_offset
        if frame_start >= 0:
            positions.append(frame_start)
        search_from = idx + len(marker)

    samples = []
    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else n
        samples.append((start, end - start))
    return samples


def is_intraframe_codec(fourcc: str) -> bool:
    """ProRes, DNxHD/DNxHR si MPEG-2-intra sunt intraframe — util in
    moov_builder pentru a marca TOATE esantioanele ca keyframe (stss
    poate fi omis complet, ceea ce inseamna 'toate sunt sync samples'
    conform specificatiei — sau poti lista explicit toate indicii)."""
    name, marker, _ = detect_codec_from_stsd_fourcc(fourcc)
    return marker is not None and fourcc != "mp2v"  # MPEG-2 poate avea B/P-frames reale
