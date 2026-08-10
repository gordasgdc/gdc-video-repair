"""
moov_builder.py — construieste un box moov nou, valid, pornind de la:
  - structura/configuratia codec-ului dintr-un track de REFERINTA (fisier
    sanatos, filmat cu aceeasi camera si aceleasi setari)
  - esantioanele REALE scanate direct din fisierul corupt (sample_scanner)

Foloseste intotdeauna co64 (offset-uri pe 64 de biti) in loc de stco, ca
sa evite orice limitare la 4GB — relevant pentru fisiere 4K/6K de camera,
care depasesc usor aceasta limita.
"""

from __future__ import annotations
import struct

from moov_parser import TrackInfo
from sample_scanner import ScannedSample


def _box(box_type: str, payload: bytes) -> bytes:
    size = 8 + len(payload)
    return struct.pack(">I4s", size, box_type.encode("latin-1")) + payload


def _full_box(box_type: str, version: int, flags: int, payload: bytes) -> bytes:
    header = struct.pack(">B3s", version, flags.to_bytes(3, "big"))
    return _box(box_type, header + payload)


def build_mvhd(timescale: int, duration: int, next_track_id: int) -> bytes:
    payload = struct.pack(">IIII", 0, 0, timescale, duration)
    payload += struct.pack(">i", 0x00010000)   # rate = 1.0
    payload += struct.pack(">h", 0x0100)        # volume = 1.0
    payload += b"\x00" * 10                     # reserved
    payload += struct.pack(">9i", 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)
    payload += b"\x00" * 24                     # pre_defined
    payload += struct.pack(">I", next_track_id)
    return _full_box("mvhd", 0, 0, payload)


def build_tkhd(track_id: int, duration: int, width: int, height: int) -> bytes:
    payload = struct.pack(">III", 0, 0, track_id)
    payload += struct.pack(">I", 0)              # reserved
    payload += struct.pack(">I", duration)
    payload += b"\x00" * 8                       # reserved
    payload += struct.pack(">h", 0)               # layer
    payload += struct.pack(">h", 0)               # alternate_group
    payload += struct.pack(">h", 0)               # volume (0 pentru video)
    payload += struct.pack(">h", 0)               # reserved
    payload += struct.pack(">9i", 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)
    payload += struct.pack(">II", width << 16, height << 16)
    return _full_box("tkhd", 0, 0x000007, payload)


def build_mdhd(timescale: int, duration: int) -> bytes:
    payload = struct.pack(">III", 0, 0, timescale)
    payload += struct.pack(">I", duration)
    payload += struct.pack(">H", 0x55C4)  # language "und"
    payload += struct.pack(">H", 0)
    return _full_box("mdhd", 0, 0, payload)


def build_hdlr(handler_type: str) -> bytes:
    payload = struct.pack(">I", 0)
    payload += handler_type.encode("latin-1")
    payload += b"\x00" * 12
    payload += b"GDC Video Repair\x00"
    return _full_box("hdlr", 0, 0, payload)


def build_vmhd() -> bytes:
    payload = struct.pack(">Hhhh", 0, 0, 0, 0)
    return _full_box("vmhd", 0, 1, payload)


def build_dref() -> bytes:
    url_box = _full_box("url ", 0, 1, b"")
    payload = struct.pack(">I", 1) + url_box
    return _full_box("dref", 0, 0, payload)


def build_dinf() -> bytes:
    return _box("dinf", build_dref())


def build_stsd_video(codec_fourcc: str, config_raw: bytes, width: int, height: int) -> bytes:
    entry_payload = b"\x00" * 6
    entry_payload += struct.pack(">H", 1)
    entry_payload += struct.pack(">H", 0)
    entry_payload += struct.pack(">H", 0)
    entry_payload += b"\x00" * 12
    entry_payload += struct.pack(">HH", width, height)
    entry_payload += struct.pack(">I", 0x00480000)
    entry_payload += struct.pack(">I", 0x00480000)
    entry_payload += struct.pack(">I", 0)
    entry_payload += struct.pack(">H", 1)
    compressorname = b"GDC Repair" + b"\x00" * (32 - len(b"GDC Repair"))
    entry_payload += compressorname[:32]
    entry_payload += struct.pack(">H", 0x0018)
    entry_payload += struct.pack(">h", -1)
    entry_payload += config_raw

    entry_box = _box(codec_fourcc, entry_payload)
    payload = struct.pack(">I", 1) + entry_box
    return _full_box("stsd", 0, 0, payload)


def build_stts(sample_count: int, sample_duration: int) -> bytes:
    payload = struct.pack(">I", 1)
    payload += struct.pack(">II", sample_count, sample_duration)
    return _full_box("stts", 0, 0, payload)


def build_stss(keyframe_indices_1based: list[int]) -> bytes:
    payload = struct.pack(">I", len(keyframe_indices_1based))
    for idx in keyframe_indices_1based:
        payload += struct.pack(">I", idx)
    return _full_box("stss", 0, 0, payload)


def build_stsc_one_sample_per_chunk(sample_count: int) -> bytes:
    payload = struct.pack(">I", 1)
    payload += struct.pack(">III", 1, 1, 1)
    return _full_box("stsc", 0, 0, payload)


def build_stsz(sample_sizes: list[int]) -> bytes:
    payload = struct.pack(">II", 0, len(sample_sizes))
    for sz in sample_sizes:
        payload += struct.pack(">I", sz)
    return _full_box("stsz", 0, 0, payload)


def build_co64(chunk_offsets: list[int]) -> bytes:
    payload = struct.pack(">I", len(chunk_offsets))
    for off in chunk_offsets:
        payload += struct.pack(">Q", off)
    return _full_box("co64", 0, 0, payload)


def build_stbl(codec_fourcc: str, config_raw: bytes, width: int, height: int,
               sample_sizes: list[int], sample_duration: int,
               keyframe_indices_1based: list[int], chunk_offsets: list[int]) -> bytes:
    parts = [
        build_stsd_video(codec_fourcc, config_raw, width, height),
        build_stts(len(sample_sizes), sample_duration),
        build_stss(keyframe_indices_1based),
        build_stsc_one_sample_per_chunk(len(sample_sizes)),
        build_stsz(sample_sizes),
        build_co64(chunk_offsets),
    ]
    return _box("stbl", b"".join(parts))


def build_minf(codec_fourcc: str, config_raw: bytes, width: int, height: int,
               sample_sizes: list[int], sample_duration: int,
               keyframe_indices_1based: list[int], chunk_offsets: list[int]) -> bytes:
    parts = [
        build_vmhd(),
        build_dinf(),
        build_stbl(codec_fourcc, config_raw, width, height, sample_sizes,
                   sample_duration, keyframe_indices_1based, chunk_offsets),
    ]
    return _box("minf", b"".join(parts))


def build_mdia(timescale: int, duration: int, codec_fourcc: str, config_raw: bytes,
               width: int, height: int, sample_sizes: list[int], sample_duration: int,
               keyframe_indices_1based: list[int], chunk_offsets: list[int]) -> bytes:
    parts = [
        build_mdhd(timescale, duration),
        build_hdlr("vide"),
        build_minf(codec_fourcc, config_raw, width, height, sample_sizes,
                   sample_duration, keyframe_indices_1based, chunk_offsets),
    ]
    return _box("mdia", b"".join(parts))


def build_trak(track_id: int, timescale: int, duration: int, codec_fourcc: str,
               config_raw: bytes, width: int, height: int, sample_sizes: list[int],
               sample_duration: int, keyframe_indices_1based: list[int],
               chunk_offsets: list[int]) -> bytes:
    parts = [
        build_tkhd(track_id, duration, width, height),
        build_mdia(timescale, duration, codec_fourcc, config_raw, width, height,
                   sample_sizes, sample_duration, keyframe_indices_1based, chunk_offsets),
    ]
    return _box("trak", b"".join(parts))


def build_moov_video_only(
    ref_track: TrackInfo,
    scanned_samples: list[ScannedSample],
    mdat_payload_start_placeholder: int = 0,
) -> bytes:
    """Construieste un moov complet, cu un singur track video, folosind
    configuratia codec-ului din ref_track (dimensiuni, avcC/hvcC) si
    esantioanele reale gasite in fisierul corupt."""
    sample_sizes = [s.size for s in scanned_samples]
    keyframe_indices = [i + 1 for i, s in enumerate(scanned_samples) if s.is_keyframe]
    if not keyframe_indices:
        keyframe_indices = [1]

    chunk_offsets = [mdat_payload_start_placeholder + s.offset for s in scanned_samples]

    st = ref_track.sample_table
    if st.time_to_sample:
        sample_duration = st.time_to_sample[0][1]
    else:
        sample_duration = ref_track.timescale // 24

    new_duration = sample_duration * len(sample_sizes)

    trak = build_trak(
        track_id=1,
        timescale=ref_track.timescale,
        duration=new_duration,
        codec_fourcc=st.codec_fourcc,
        config_raw=st.codec_config_raw,
        width=st.width,
        height=st.height,
        sample_sizes=sample_sizes,
        sample_duration=sample_duration,
        keyframe_indices_1based=keyframe_indices,
        chunk_offsets=chunk_offsets,
    )

    mvhd = build_mvhd(ref_track.timescale, new_duration, next_track_id=2)
    return _box("moov", mvhd + trak)
