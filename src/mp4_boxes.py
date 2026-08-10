"""
mp4_boxes.py — primitive de citire a structurii de "boxuri" (atomi) MP4/MOV.

Formatul ISO Base Media (MP4/MOV/M4V etc.) e o structură de tip "box":
    4 octeți  size (big-endian, include header-ul)
    4 octeți  type (4 caractere ASCII, ex. "moov", "mdat", "ftyp")
    (size-8) octeți  payload
Excepții:
    size == 1  -> urmeaza 8 octeți de "largesize" (pentru boxuri > 4GB)
    size == 0  -> boxul se întinde până la finalul fișierului
"""

from __future__ import annotations
import struct
from dataclasses import dataclass, field
from typing import BinaryIO, Optional


HEADER_SIZE = 8
LARGESIZE_EXTRA = 8

# Boxuri care sunt "containere" — payload-ul lor e o listă de alte boxuri,
# nu date brute. Esențial de știut ca să navigăm corect în structură.
CONTAINER_BOX_TYPES = {
    "moov", "trak", "mdia", "minf", "stbl", "edts", "mvex", "moof",
    "traf", "udta", "meta", "dinf", "ipro", "sinf", "schi",
}


@dataclass
class Box:
    box_type: str
    start: int          # offset absolut in fisier, unde incepe header-ul
    header_size: int     # 8 (normal) sau 16 (largesize)
    payload_size: int    # dimensiunea payload-ului, fara header
    payload_start: int   # offset absolut unde incepe payload-ul
    children: list["Box"] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return self.header_size + self.payload_size

    @property
    def end(self) -> int:
        return self.payload_start + self.payload_size

    def find(self, path: str) -> Optional["Box"]:
        """Cauta un box descendent dupa o cale de tipul 'trak/mdia/minf/stbl'."""
        parts = path.split("/")
        current = self
        for part in parts:
            match = next((c for c in current.children if c.box_type == part), None)
            if match is None:
                return None
            current = match
        return current

    def find_all(self, box_type: str) -> list["Box"]:
        """Cauta toti descendentii directi + indirecti cu un anumit tip."""
        results = []
        for c in self.children:
            if c.box_type == box_type:
                results.append(c)
            results.extend(c.find_all(box_type))
        return results


def read_box_header(f: BinaryIO, offset: int, limit: int) -> Optional[Box]:
    """Citeste header-ul unui singur box de la offset-ul dat. Intoarce None
    daca nu mai incape un header valid pana la limit (sfarsitul parintelui
    sau al fisierului)."""
    if offset + HEADER_SIZE > limit:
        return None
    f.seek(offset)
    raw = f.read(HEADER_SIZE)
    if len(raw) < HEADER_SIZE:
        return None
    size, box_type_bytes = struct.unpack(">I4s", raw)
    box_type = box_type_bytes.decode("latin-1")
    header_size = HEADER_SIZE

    if size == 1:
        raw_large = f.read(LARGESIZE_EXTRA)
        if len(raw_large) < LARGESIZE_EXTRA:
            return None
        (size,) = struct.unpack(">Q", raw_large)
        header_size = HEADER_SIZE + LARGESIZE_EXTRA
    elif size == 0:
        size = limit - offset

    if size < header_size:
        # box invalid/corupt - dimensiune imposibila
        return None

    payload_size = size - header_size
    payload_start = offset + header_size

    return Box(
        box_type=box_type,
        start=offset,
        header_size=header_size,
        payload_size=payload_size,
        payload_start=payload_start,
    )


def parse_boxes(f: BinaryIO, start: int, end: int, recurse_containers: bool = True) -> list[Box]:
    """Parseaza toate boxurile de nivel superior din intervalul [start, end).
    Pentru boxurile container (moov, trak, etc.), coboara recursiv si
    populeaza .children."""
    boxes = []
    offset = start
    while offset < end:
        box = read_box_header(f, offset, end)
        if box is None:
            break
        if recurse_containers and box.box_type in CONTAINER_BOX_TYPES:
            box.children = parse_boxes(f, box.payload_start, box.end, recurse_containers=True)
        boxes.append(box)
        offset = box.end
    return boxes


def parse_file(path: str) -> list[Box]:
    """Parseaza toata structura de top-level a unui fisier MP4/MOV."""
    with open(path, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()
        return parse_boxes(f, 0, file_size, recurse_containers=True)


def read_payload(path: str, box: Box) -> bytes:
    """Citeste payload-ul brut al unui box (nerecursiv - pentru boxuri
    frunza ca mdat, sau pentru boxuri container ale caror octeti bruti
    vrei sa-i copiezi ca atare)."""
    with open(path, "rb") as f:
        f.seek(box.payload_start)
        return f.read(box.payload_size)


def summarize(boxes: list[Box], indent: int = 0) -> str:
    """Reprezentare text a structurii, utila pentru depanare."""
    lines = []
    for b in boxes:
        lines.append(f"{'  ' * indent}{b.box_type}  size={b.total_size}  @{b.start}")
        if b.children:
            lines.append(summarize(b.children, indent + 1))
    return "\n".join(lines)
