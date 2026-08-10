"""
moov_parser.py — extrage valorile efective din boxurile de sample-table
(stsd, stts, stsz, stco/co64, stsc, stss) si din header-ele de track/media,
pornind de la structura deja identificata de mp4_boxes.py.

Referinta campurilor: ISO/IEC 14496-12 (ISOBMFF).
"""

from __future__ import annotations
import struct
from dataclasses import dataclass, field
from typing import Optional

import mp4_boxes
from mp4_boxes import Box


@dataclass
class SampleTable:
    # stsz: dimensiunea (in octeti) a fiecarui esantion
    sample_sizes: list[int] = field(default_factory=list)
    # stco/co64: offset-ul absolut (in fisier) al fiecarui "chunk"
    chunk_offsets: list[int] = field(default_factory=list)
    # stsc: pentru fiecare grup de chunk-uri incepand cu first_chunk,
    #       cate esantioane contine fiecare chunk din grup
    # lista de tupluri (first_chunk, samples_per_chunk, sample_desc_index)
    sample_to_chunk: list[tuple[int, int, int]] = field(default_factory=list)
    # stts: lista de (sample_count, sample_delta) - durata fiecarui esantion
    time_to_sample: list[tuple[int, int]] = field(default_factory=list)
    # stss: indicii (1-based) ai esantioanelor cheie (keyframe / IDR)
    sync_samples: list[int] = field(default_factory=list)
    # stsd: codec-ul (fourCC) + payload-ul brut de configurare (avcC/hvcC etc.)
    codec_fourcc: str = ""
    codec_config_raw: bytes = b""
    # dimensiuni video, daca e track video
    width: int = 0
    height: int = 0


@dataclass
class TrackInfo:
    track_id: int = 0
    handler_type: str = ""     # "vide" sau "soun"
    timescale: int = 0
    duration: int = 0
    sample_table: SampleTable = field(default_factory=SampleTable)


def _read_box_payload(path: str, box: Box) -> bytes:
    return mp4_boxes.read_payload(path, box)


def parse_stsz(payload: bytes) -> list[int]:
    # version(1) + flags(3) + sample_size(4) + sample_count(4) + [entries...]
    _, sample_size, sample_count = struct.unpack(">IiI", payload[0:12])
    # nota: sample_size citit ca 'i' dar e de fapt uint32 fara semn logic;
    # folosim direct urmatorul camp daca sample_size==0 (marime variabila)
    sample_size_u = struct.unpack(">I", payload[4:8])[0]
    if sample_size_u != 0:
        # toate esantioanele au aceeasi dimensiune fixa
        return [sample_size_u] * sample_count
    sizes = []
    offset = 12
    for _ in range(sample_count):
        (sz,) = struct.unpack(">I", payload[offset:offset + 4])
        sizes.append(sz)
        offset += 4
    return sizes


def parse_stco(payload: bytes) -> list[int]:
    _, entry_count = struct.unpack(">II", payload[0:8])
    offsets = []
    off = 8
    for _ in range(entry_count):
        (v,) = struct.unpack(">I", payload[off:off + 4])
        offsets.append(v)
        off += 4
    return offsets


def parse_co64(payload: bytes) -> list[int]:
    _, entry_count = struct.unpack(">II", payload[0:8])
    offsets = []
    off = 8
    for _ in range(entry_count):
        (v,) = struct.unpack(">Q", payload[off:off + 8])
        offsets.append(v)
        off += 8
    return offsets


def parse_stsc(payload: bytes) -> list[tuple[int, int, int]]:
    _, entry_count = struct.unpack(">II", payload[0:8])
    entries = []
    off = 8
    for _ in range(entry_count):
        first_chunk, samples_per_chunk, sample_desc_idx = struct.unpack(">III", payload[off:off + 12])
        entries.append((first_chunk, samples_per_chunk, sample_desc_idx))
        off += 12
    return entries


def parse_stts(payload: bytes) -> list[tuple[int, int]]:
    _, entry_count = struct.unpack(">II", payload[0:8])
    entries = []
    off = 8
    for _ in range(entry_count):
        count, delta = struct.unpack(">II", payload[off:off + 8])
        entries.append((count, delta))
        off += 8
    return entries


def parse_stss(payload: bytes) -> list[int]:
    _, entry_count = struct.unpack(">II", payload[0:8])
    entries = []
    off = 8
    for _ in range(entry_count):
        (idx,) = struct.unpack(">I", payload[off:off + 4])
        entries.append(idx)
        off += 4
    return entries


def parse_stsd_video(payload: bytes) -> tuple[str, bytes, int, int]:
    """Extrage fourCC-ul codecului video, blocul de configurare brut
    (ex. avcC/hvcC, inclus ca sub-box), si dimensiunile."""
    # version(1)+flags(3) + entry_count(4)
    entry_count = struct.unpack(">I", payload[4:8])[0]
    off = 8
    if entry_count == 0:
        return "", b"", 0, 0
    # VisualSampleEntry: size(4)+type(4)+reserved(6)+data_ref_index(2)
    #   + reserved fields + width(2)+height(2) + ... + compressorname(32) + depth(2) + pre_defined(2)
    entry_size, entry_type_b = struct.unpack(">I4s", payload[off:off + 8])
    entry_type = entry_type_b.decode("latin-1")
    entry_payload = payload[off + 8: off + entry_size]
    # in interiorul VisualSampleEntry: reserved(6)+data_ref_index(2)=8,
    # apoi pre_defined(2)+reserved(2)+pre_defined(12)=16, apoi width(2)+height(2)
    width, height = struct.unpack(">HH", entry_payload[24:28])
    # restul campurilor fixe ale VisualSampleEntry (pana la sub-boxuri gen avcC/hvcC)
    # dupa width/height(4) urmeaza: horizresolution(4)+vertresolution(4)+reserved(4)
    #   +frame_count(2)+compressorname(32)+depth(2)+pre_defined(2) = 50 octeti
    fixed_fields_after_wh = 4 + 4 + 4 + 2 + 32 + 2 + 2
    sub_boxes_start = 28 + fixed_fields_after_wh
    sub_payload = entry_payload[sub_boxes_start:]
    # in interiorul acestui payload, cautam avcC/hvcC ca sub-box
    config_raw = b""
    off2 = 0
    while off2 + 8 <= len(sub_payload):
        sub_size, sub_type_b = struct.unpack(">I4s", sub_payload[off2:off2 + 8])
        sub_type = sub_type_b.decode("latin-1")
        if sub_type in ("avcC", "hvcC"):
            config_raw = sub_payload[off2:off2 + sub_size]
            break
        if sub_size < 8:
            break
        off2 += sub_size
    return entry_type, config_raw, width, height


def parse_track(path: str, trak_box: Box) -> Optional[TrackInfo]:
    mdia = trak_box.find("mdia")
    if mdia is None:
        return None
    mdhd = mdia.find("mdhd")
    hdlr = mdia.find("hdlr")
    stbl = mdia.find("minf/stbl")
    if mdhd is None or hdlr is None or stbl is None:
        return None

    mdhd_payload = _read_box_payload(path, mdhd)
    version = mdhd_payload[0]
    if version == 1:
        timescale, duration = struct.unpack(">IQ", mdhd_payload[20:32])
    else:
        timescale, duration = struct.unpack(">II", mdhd_payload[12:20])

    hdlr_payload = _read_box_payload(path, hdlr)
    handler_type = hdlr_payload[8:12].decode("latin-1")

    table = SampleTable()

    stsd = stbl.find("stsd")
    if stsd is not None and handler_type == "vide":
        codec_fourcc, config_raw, width, height = parse_stsd_video(_read_box_payload(path, stsd))
        table.codec_fourcc = codec_fourcc
        table.codec_config_raw = config_raw
        table.width = width
        table.height = height

    stsz = stbl.find("stsz")
    if stsz is not None:
        table.sample_sizes = parse_stsz(_read_box_payload(path, stsz))

    stco = stbl.find("stco")
    co64 = stbl.find("co64")
    if stco is not None:
        table.chunk_offsets = parse_stco(_read_box_payload(path, stco))
    elif co64 is not None:
        table.chunk_offsets = parse_co64(_read_box_payload(path, co64))

    stsc = stbl.find("stsc")
    if stsc is not None:
        table.sample_to_chunk = parse_stsc(_read_box_payload(path, stsc))

    stts = stbl.find("stts")
    if stts is not None:
        table.time_to_sample = parse_stts(_read_box_payload(path, stts))

    stss = stbl.find("stss")
    if stss is not None:
        table.sync_samples = parse_stss(_read_box_payload(path, stss))

    tkhd = trak_box.find("tkhd")
    track_id = 0
    if tkhd is not None:
        tkhd_payload = _read_box_payload(path, tkhd)
        v = tkhd_payload[0]
        if v == 1:
            track_id = struct.unpack(">I", tkhd_payload[20:24])[0]
        else:
            track_id = struct.unpack(">I", tkhd_payload[12:16])[0]

    return TrackInfo(
        track_id=track_id,
        handler_type=handler_type,
        timescale=timescale,
        duration=duration,
        sample_table=table,
    )


def parse_all_tracks(path: str, boxes: list[Box]) -> list[TrackInfo]:
    moov = next((b for b in boxes if b.box_type == "moov"), None)
    if moov is None:
        return []
    tracks = []
    for trak in moov.find_all("trak"):
        info = parse_track(path, trak)
        if info is not None:
            tracks.append(info)
    return tracks
