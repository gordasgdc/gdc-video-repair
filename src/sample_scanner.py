"""
sample_scanner.py — scaneaza date brute (tipic continutul unui box mdat)
pentru a identifica granitele individuale ale esantioanelor (cadrelor),
cand tabela stsz/stco din moov lipseste sau e coruptă.

Ideea centrala: in interiorul unui mdat MP4/MOV, esantioanele video H.264/
H.265 NU sunt in format Annex-B (cu start code-uri 00 00 00 01) — sunt
"length-prefixed": 4 octeti big-endian cu lungimea NAL-ului, urmati de
octetii NAL-ului propriu-zis, repetat. Asta inseamna ca, daca structura
interna a mdat-ului a ramas intacta (foarte frecvent — camera scrie mdat
incremental in timpul filmarii, si scrie moov abia la finalul inregistrarii;
scoaterea cardului in timpul filmarii lasa mdat perfect valid, doar moov
lipseste complet), putem enumera esantioanele parcurgand aceasta structura
direct, fara sa avem nevoie de stsz/stco deloc.
"""

from __future__ import annotations
import struct
from dataclasses import dataclass


@dataclass
class ScannedSample:
    offset: int       # offset absolut in fisier unde incepe esantionul (include length-prefix-urile NAL)
    size: int          # dimensiunea totala a esantionului, in octeti
    is_keyframe: bool  # daca esantionul contine un NAL de tip IDR/keyframe


def _h264_nal_type(first_byte: int) -> int:
    return first_byte & 0x1F


def _h265_nal_type(first_byte: int) -> int:
    return (first_byte >> 1) & 0x3F


def _h264_is_vcl(nal_type: int) -> bool:
    # tipurile 1-5 sunt slice-uri (date de imagine reala); restul (SPS=7,
    # PPS=8, SEI=6, AUD=9 etc.) sunt NAL-uri "non-VCL" care preced si
    # apartin de fapt aceluiasi esantion ca slice-ul care le urmeaza.
    return 1 <= nal_type <= 5


def _h265_is_vcl(nal_type: int) -> bool:
    # tipurile 0-31 sunt slice-uri VCL in H.265; VPS=32, SPS=33, PPS=34,
    # SEI=39/40 etc. sunt non-VCL si apartin esantionului urmator.
    return 0 <= nal_type <= 31


def scan_length_prefixed_samples(
    data: bytes,
    is_hevc: bool,
    max_samples: int = 2_000_000,
) -> list[ScannedSample]:
    """Parcurge octeti bruti (continutul unui mdat, sau tot ce a mai
    ramas dintr-un fisier corupt) si grupeaza NAL-urile length-prefixed
    in esantioane (cadre) corecte: orice NAL-uri non-VCL (SPS/PPS/SEI/
    AUD) care preced un NAL VCL (slice) apartin aceluiasi esantion ca
    acel slice — exact cum grupeaza si muxer-ele reale QuickTime/MP4 un
    "access unit" intr-un singur esantion in stsz. Verificat direct
    impotriva stsz-ului real al unui fisier intact (vezi test din
    suita de teste) — potrivire exacta, octet cu octet."""
    samples: list[ScannedSample] = []
    offset = 0
    n = len(data)

    pending_start = None    # offset-ul unde incepe esantionul curent (in curs de acumulare)
    pending_has_key = False

    while offset + 4 <= n and len(samples) < max_samples:
        (nal_len,) = struct.unpack(">I", data[offset:offset + 4])

        if nal_len == 0 or nal_len > n - offset - 4:
            break

        nal_start = offset + 4
        first_byte = data[nal_start]
        if is_hevc:
            nal_type = _h265_nal_type(first_byte)
            is_vcl = _h265_is_vcl(nal_type)
            is_key = nal_type in (19, 20, 21)
        else:
            nal_type = _h264_nal_type(first_byte)
            is_vcl = _h264_is_vcl(nal_type)
            is_key = nal_type == 5

        if pending_start is None:
            pending_start = offset
        if is_key:
            pending_has_key = True

        nal_end = nal_start + nal_len

        if is_vcl:
            # acest NAL incheie esantionul curent (access unit complet)
            samples.append(ScannedSample(
                offset=pending_start,
                size=nal_end - pending_start,
                is_keyframe=pending_has_key,
            ))
            pending_start = None
            pending_has_key = False

        offset = nal_end

    # daca au mai ramas NAL-uri non-VCL neincheiate la finalul datelor
    # (rar, dar posibil la finalul unui fisier trunchiat), le atasam ca
    # esantion final, mai bine decat sa le pierdem complet.
    if pending_start is not None and offset > pending_start:
        samples.append(ScannedSample(offset=pending_start, size=offset - pending_start, is_keyframe=pending_has_key))

    return samples


def merge_samples_by_reference_pattern(
    raw_samples: list[ScannedSample],
    ref_samples_per_frame_hint: int = 1,
) -> list[ScannedSample]:
    """Daca fiecare NAL a fost tratat ca esantion separat dar cadrele
    reale contineau mai multe NAL-uri (ex. SEI + slice), aceasta functie
    le regrupeaza in cate 'ref_samples_per_frame_hint' NAL-uri per cadru
    de output. Pentru marea majoritate a inregistrarilor de camera
    (un NAL de slice per cadru), hint-ul e 1 si functia e un no-op."""
    if ref_samples_per_frame_hint <= 1:
        return raw_samples
    merged = []
    i = 0
    while i < len(raw_samples):
        group = raw_samples[i:i + ref_samples_per_frame_hint]
        if not group:
            break
        total_size = sum(s.size for s in group)
        is_key = any(s.is_keyframe for s in group)
        merged.append(ScannedSample(offset=group[0].offset, size=total_size, is_keyframe=is_key))
        i += ref_samples_per_frame_hint
    return merged
