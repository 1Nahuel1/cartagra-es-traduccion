#!/usr/bin/env python3
"""Extract/repack MGPK archives (Cartagra / Innocent Grey PAC files)."""
import struct
import sys
import zlib
from pathlib import Path


def read_entries(data):
    magic, version, count = struct.unpack_from("<4sII", data, 0)
    if magic != b"MGPK":
        raise ValueError("not an MGPK file")
    entries = []
    pos = 12
    for _ in range(count):
        name_len = data[pos]
        name = data[pos + 1 : pos + 1 + name_len].decode("utf-8")
        offset, size = struct.unpack_from("<II", data, pos + 0x20)
        entries.append({"name": name, "offset": offset, "size": size})
        pos += 0x30
    return version, entries


def file_payload(data, entry):
    blob = data[entry["offset"] : entry["offset"] + entry["size"]]
    if blob[:2] in (b"\x78\x9c", b"\x78\x01", b"\x78\xda", b"\x78\x5e"):
        try:
            return zlib.decompress(blob)
        except zlib.error:
            pass
    return blob


def extract(pac_path, out_dir):
    data = Path(pac_path).read_bytes()
    version, entries = read_entries(data)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for e in entries:
        payload = file_payload(data, e)
        dest = out / e["name"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
    print(f"extracted {len(entries)} files (version {version})")


def repack(pac_path_in, pac_path_out, dir_with_files):
    src = Path(pac_path_in).read_bytes()
    version, entries = read_entries(src)
    files_dir = Path(dir_with_files)

    blobs = []
    header = bytearray()
    header += struct.pack("<4sII", b"MGPK", version, len(entries))
    header += b"\x00" * (0x30 * len(entries))

    pos = len(header)
    for i, e in enumerate(entries):
        payload = (files_dir / e["name"]).read_bytes()
        # re-compress with zlib if original was compressed
        orig = src[e["offset"] : e["offset"] + e["size"]]
        if orig[:2] in (b"\x78\x9c", b"\x78\x01", b"\x78\xda", b"\x78\x5e"):
            payload = zlib.compress(payload, 9)
        blobs.append(payload)
        name_bytes = e["name"].encode("utf-8")
        if len(name_bytes) > 0x1F:
            raise ValueError(f"name too long: {e['name']}")
        entry = bytearray(0x30)
        entry[0] = len(name_bytes)
        entry[1 : 1 + len(name_bytes)] = name_bytes
        struct.pack_into("<II", entry, 0x20, pos, len(payload))
        header[12 + i * 0x30 : 12 + (i + 1) * 0x30] = entry
        pos += len(payload)

    Path(pac_path_out).write_bytes(bytes(header) + b"".join(blobs))
    print(f"repacked {len(entries)} files -> {pac_path_out}")


if __name__ == "__main__":
    if sys.argv[1] == "x":
        extract(sys.argv[2], sys.argv[3])
    else:
        repack(sys.argv[2], sys.argv[3], sys.argv[4])
