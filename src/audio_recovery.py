"""
audio_recovery.py — extensii pentru suportul audio in GDC Video Repair v2.0.

Contine trei categorii de functii, gandite sa se integreze in fisierele
existente fara sa le rescrie:

  1. Extensii pentru moov_parser.py — citirea configuratiei audio din
     REFERINTA (stsd 'mp4a'/'twos'/'lpcm', esds, canale, bitrate).
  2. O functie de clasificare CBR/VBR, care decide daca audio-ul poate
     fi reconstruit sau nu, INAINTE sa incerci — evita sa produci
     fisiere cu audio stricat care par ok.
  3. Extensii pentru moov_builder.py — stsd audio, smhd, si taierea
     efectiva a golurilor din mdat in esantioane audio.
  4. O functie de separare video/audio in mdat, bazata pe golurile
     dintre esantioanele video deja scanate de sample_scanner.py.

Integrare:
  - Codul din sectiunea (1) se adauga in moov_parser.py, langa
    parse_stsd_video existent.
  - Codul din sectiunea (3) se adauga in moov_builder.py, langa
    build_stsd_video existent.
  - repair_engine.py apeleaza clasify_audio_recoverability() INAINTE
    sa incerce reconstructia audio, si raporteaza clar in UI daca
    audio e VBR si deci nerecuperabil.
"""

from __future__ import annotations
import struct
from dataclasses import dataclass, field

import mp4_boxes
from mp4_boxes import Box


# ---------------------------------------------------------------------
# 1. moov_parser.py — citirea configuratiei audio din REFERINTA
# ---------------------------------------------------------------------

def parse_stsz_full(payload: bytes) -> tuple[int, list[int]]:
    """La fel ca moov_parser.parse_stsz(), dar intoarce si sample_size
    fix (0 daca variaza) — necesar pentru clasificarea CBR/VBR de mai jos.
    Daca ai deja parse_stsz in moov_parser.py, poti sa-l folosesti direct
    si sa recalculezi fixed size separat; il am aici complet pentru
    claritate."""
    _, sample_size, sample_count = struct.unpack(">III", payload[0:12])
    if sample_size != 0:
        return sample_size, [sample_size] * sample_count
    sizes = []
    offset = 12
    for _ in range(sample_count):
        (sz,) = struct.unpack(">I", payload[offset:offset + 4])
        sizes.append(sz)
        offset += 4
    return 0, sizes


def parse_stsd_audio(payload: bytes) -> dict:
    """Extrage fourCC-ul codecului audio, numarul de canale, bitii per
    esantion, si sample rate-ul, dintr-un stsd cu handler_type 'soun'.

    Structura AudioSampleEntry (ISO/IEC 14496-12 §12.2.3):
      size(4)+type(4) + reserved(6)+data_ref_index(2)
      + reserved(8) + channelcount(2) + samplesize(2)
      + pre_defined(2)+reserved(2) + samplerate(4, fixed-point 16.16)
      + [sub-boxes: esds pentru AAC, sau nimic pentru lpcm/twos]
    """
    entry_count = struct.unpack(">I", payload[4:8])[0]
    if entry_count == 0:
        return {}
    off = 8
    entry_size, entry_type_b = struct.unpack(">I4s", payload[off:off + 8])
    entry_type = entry_type_b.decode("latin-1")
    entry_payload = payload[off + 8: off + entry_size]

    # dupa reserved(6)+data_ref_index(2) = 8 octeti, urmeaza campurile audio
    fixed = entry_payload[8:28]
    channel_count, sample_size_bits = struct.unpack(">HH", fixed[8:12])
    sample_rate_fixed = struct.unpack(">I", fixed[16:20])[0]
    sample_rate = sample_rate_fixed >> 16

    # cauta esds (config AAC: profil, sample rate index, canale) ca sub-box
    sub_payload = entry_payload[28:]
    esds_raw = b""
    off2 = 0
    while off2 + 8 <= len(sub_payload):
        sub_size, sub_type_b = struct.unpack(">I4s", sub_payload[off2:off2 + 8])
        sub_type = sub_type_b.decode("latin-1")
        if sub_type == "esds":
            esds_raw = sub_payload[off2:off2 + sub_size]
            break
        if sub_size < 8:
            break
        off2 += sub_size

    return {
        "codec_fourcc": entry_type,          # 'mp4a' (AAC), 'lpcm'/'twos'/'sowt' (PCM)
        "channel_count": channel_count,
        "sample_size_bits": sample_size_bits,
        "sample_rate": sample_rate,
        "esds_raw": esds_raw,
        "is_pcm": entry_type in ("lpcm", "twos", "sowt", "in24", "in32"),
    }


def parse_audio_track(path: str, trak_box: Box) -> dict | None:
    """Analog cu moov_parser.parse_track(), dar specializat pentru
    track-uri audio ('soun'). Adauga si informatia stsz completa,
    necesara pentru clasificarea CBR/VBR."""
    mdia = trak_box.find("mdia")
    if mdia is None:
        return None
    hdlr = mdia.find("hdlr")
    stbl = mdia.find("minf/stbl")
    if hdlr is None or stbl is None:
        return None

    hdlr_payload = mp4_boxes.read_payload(path, hdlr)
    handler_type = hdlr_payload[8:12].decode("latin-1")
    if handler_type != "soun":
        return None

    stsd = stbl.find("stsd")
    audio_config = parse_stsd_audio(mp4_boxes.read_payload(path, stsd)) if stsd else {}

    stsz = stbl.find("stsz")
    fixed_size, sample_sizes = (0, [])
    if stsz is not None:
        fixed_size, sample_sizes = parse_stsz_full(mp4_boxes.read_payload(path, stsz))

    mdhd = mdia.find("mdhd")
    timescale = 0
    if mdhd is not None:
        mdhd_payload = mp4_boxes.read_payload(path, mdhd)
        version = mdhd_payload[0]
        if version == 1:
            timescale = struct.unpack(">I", mdhd_payload[20:24])[0]
        else:
            timescale = struct.unpack(">I", mdhd_payload[12:16])[0]

    return {
        "audio_config": audio_config,
        "timescale": timescale,
        "fixed_sample_size": fixed_size,
        "sample_sizes": sample_sizes,
    }


# ---------------------------------------------------------------------
# 2. Clasificare CBR/VBR — decide DACA merita incercat deloc
# ---------------------------------------------------------------------

@dataclass
class AudioRecoverability:
    recoverable: bool
    reason: str
    strategy: str = ""          # "pcm_fixed" | "aac_estimated_cbr" | ""
    estimated_frame_size: int = 0


def classify_audio_recoverability(ref_audio: dict, variance_threshold: float = 0.05) -> AudioRecoverability:
    """Decide daca merita incercata reconstructia audio, PE BAZA
    fisierului de REFERINTA (nu a celui corupt — acolo stsz-ul deja nu
    exista, de-asta suntem in situatia asta). Trebuie apelata inainte
    de orice incercare de reconstructie audio."""
    cfg = ref_audio.get("audio_config", {})
    if not cfg:
        return AudioRecoverability(False, "Referinta nu are track audio identificabil.")

    if cfg.get("is_pcm"):
        bytes_per_sample = cfg["channel_count"] * (cfg["sample_size_bits"] // 8)
        return AudioRecoverability(True, "Audio PCM — dimensiune fixa, recuperare fiabila.",
                                    strategy="pcm_fixed", estimated_frame_size=bytes_per_sample)

    sizes = ref_audio.get("sample_sizes", [])
    if len(sizes) < 8:
        return AudioRecoverability(False, "Prea putine esantioane in referinta ca sa evaluam variatia bitrate-ului.")

    avg = sum(sizes) / len(sizes)
    variance = sum(abs(s - avg) for s in sizes) / len(sizes) / avg if avg else 1.0

    if variance <= variance_threshold:
        return AudioRecoverability(
            True,
            f"AAC aproape-CBR detectat in referinta (variatie {variance:.1%}) — "
            "reconstructie posibila, dar aproximativa (risc de drift de sincronizare pe fisiere lungi).",
            strategy="aac_estimated_cbr",
            estimated_frame_size=round(avg),
        )

    return AudioRecoverability(
        False,
        f"AAC cu bitrate variabil detectat in referinta (variatie {variance:.1%}). "
        "Fara tabela stsz din fisierul original, granitele dintre frame-uri audio "
        "nu pot fi determinate — reconstructia ar produce audio stricat. "
        "Fisierul va fi reparat doar pe partea video.",
    )


# ---------------------------------------------------------------------
# 3. Separarea video/audio in mdat, folosind golurile dintre esantioanele
#    video deja scanate de sample_scanner.py
# ---------------------------------------------------------------------

def extract_audio_gaps(mdat_data: bytes, video_samples: list, min_gap_size: int = 8) -> list[tuple[int, int]]:
    """Presupune interleaving simplu [video][audio][video][audio]...
    in mdat, si intoarce lista de (offset, size) pentru fiecare gol
    dintre esantioane video consecutive — candidati pentru chunk-uri
    audio. video_samples e lista de ScannedSample din sample_scanner.py,
    deja sortata dupa offset."""
    gaps = []
    for i in range(len(video_samples) - 1):
        end_of_this = video_samples[i].offset + video_samples[i].size
        start_of_next = video_samples[i + 1].offset
        gap_size = start_of_next - end_of_this
        if gap_size >= min_gap_size:
            gaps.append((end_of_this, gap_size))
    return gaps


def slice_audio_gaps_to_samples(mdat_data: bytes, gaps: list[tuple[int, int]],
                                 frame_size: int) -> list[tuple[int, int]]:
    """Taie fiecare gol audio in esantioane de marime fixa (PCM real,
    sau AAC 'estimat-CBR'). Intoarce lista de (offset_absolut, size).
    Orice rest mai mic decat un frame la finalul unui gol e ignorat —
    de obicei e padding de aliniere, nu date utile."""
    samples = []
    for gap_offset, gap_size in gaps:
        n_frames = gap_size // frame_size
        for i in range(n_frames):
            samples.append((gap_offset + i * frame_size, frame_size))
    return samples


# ---------------------------------------------------------------------
# 4. moov_builder.py — stsd audio + smhd
# ---------------------------------------------------------------------

def _box(box_type: str, payload: bytes) -> bytes:
    size = 8 + len(payload)
    return struct.pack(">I4s", size, box_type.encode("latin-1")) + payload


def _full_box(box_type: str, version: int, flags: int, payload: bytes) -> bytes:
    header = struct.pack(">B3s", version, flags.to_bytes(3, "big"))
    return _box(box_type, header + payload)


def build_smhd() -> bytes:
    """Sound Media Header — echivalentul lui vmhd, dar pentru audio."""
    payload = struct.pack(">hh", 0, 0)  # balance + reserved
    return _full_box("smhd", 0, 0, payload)


def build_stsd_audio(codec_fourcc: str, channel_count: int, sample_size_bits: int,
                      sample_rate: int, esds_raw: bytes) -> bytes:
    entry_payload = b"\x00" * 6
    entry_payload += struct.pack(">H", 1)          # data_reference_index
    entry_payload += b"\x00" * 8                    # reserved (2x uint32)
    entry_payload += struct.pack(">HH", channel_count, sample_size_bits)
    entry_payload += struct.pack(">Hh", 0, 0)        # pre_defined + reserved
    entry_payload += struct.pack(">I", sample_rate << 16)
    entry_payload += esds_raw                        # gol pentru PCM, esds pentru AAC

    entry_box = _box(codec_fourcc, entry_payload)
    payload = struct.pack(">I", 1) + entry_box
    return _full_box("stsd", 0, 0, payload)


def build_stsz_audio(sample_size_and_count: tuple[int, int] | None, explicit_sizes: list[int] | None = None) -> bytes:
    """Pentru audio de dimensiune fixa (PCM sau AAC estimat-CBR),
    foloseste calea rapida cu sample_size uniform (fara sa listezi
    fiecare esantion individual) — la fel cum face stsz nativ pentru
    PCM in fisiere sanatoase."""
    if explicit_sizes:
        payload = struct.pack(">II", 0, len(explicit_sizes))
        for sz in explicit_sizes:
            payload += struct.pack(">I", sz)
        return _full_box("stsz", 0, 0, payload)
    size, count = sample_size_and_count
    payload = struct.pack(">II", size, count)
    return _full_box("stsz", 0, 0, payload)
