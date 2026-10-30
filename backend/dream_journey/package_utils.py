"""Lossless file preparation shared by dataset adapters."""

import struct
from pathlib import Path
from tempfile import NamedTemporaryFile


def image_dimensions(data: bytes) -> tuple[int, int]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("Expected a PNG or JPEG image")
    position = 2
    while position + 4 < len(data):
        if data[position] != 0xFF:
            position += 1
            continue
        while data[position] == 0xFF:
            position += 1
        marker = data[position]
        position += 1
        length = int.from_bytes(data[position : position + 2], "big")
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height, width = struct.unpack(">HH", data[position + 3 : position + 7])
            return width, height
        if length < 2:
            break
        position += length
    raise ValueError("Cannot read JPEG dimensions")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(data)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)
