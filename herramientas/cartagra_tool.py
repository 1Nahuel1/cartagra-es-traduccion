#!/usr/bin/env python3
"""Cartagra script tool: decrypt/encrypt, extract/insert dialogue.

Pipeline per file (from GameAssetManager.KeyEncode + CLZF2):
  disk -> XOR rolling 11-byte key (+27/byte) -> LZF decompress -> text
  text -> LZF compress -> XOR rolling -> disk
"""
import argparse
import os
import re
import struct
import sys
from pathlib import Path

KEY = bytes([229, 101, 186, 26, 61, 198, 127, 158, 70, 21, 137])


def keyencode(data, decrypt=True):
    key = bytearray(KEY)
    out = bytearray(data)
    for i in range(len(out)):
        out[i] ^= key[i % 11]
        key[i % 11] = (key[i % 11] + 27) & 0xFF
    return bytes(out)


def lzf_decompress(inp):
    out = bytearray(len(inp) * 8)
    ip = 0
    op = 0
    n = len(inp)
    while ip < n:
        ctrl = inp[ip]
        ip += 1
        if ctrl < 32:
            length = ctrl + 1
            if op + length > len(out):
                out.extend(bytearray(op + length - len(out) + 4096))
            out[op : op + length] = inp[ip : ip + length]
            op += length
            ip += length
        else:
            length = ctrl >> 5
            ref = op - ((ctrl & 0x1F) << 8) - 1
            if length == 7:
                length += inp[ip]
                ip += 1
            ref -= inp[ip]
            ip += 1
            length += 2
            if op + length > len(out):
                out.extend(bytearray(op + length - len(out) + 4096))
            if ref < 0:
                raise ValueError(f"bad LZF backref at ip={ip} op={op}")
            for _ in range(length):
                out[op] = out[ref]
                op += 1
                ref += 1
    return bytes(out[:op])


def lzf_compress(inp):
    """Compress with a byte-exact port of CLZF2 (Unity's liblzf 2.1).

    Using the external `lzf` (liblzf) module produces bitstreams that differ
    from CLZF2 for some back-references, which makes the game's decompressor
    read garbage and hang. This pure-Python port matches CLZF2 exactly.
    """
    return _clzf2_compress(inp)


HLOG = 13
HSIZE = 1 << HLOG
MAX_LIT = 1 << 5
MAX_OFF = 1 << 13
MAX_REF = (1 << 8) + (1 << 3)


def _clzf2_compress(inp):
    n = len(inp)
    if n == 0:
        return b""
    if n <= 2:
        return bytes([n - 1]) + bytes(inp)

    out = bytearray(n + n // 16 + 64 + 3)
    htab = [0] * HSIZE
    ip = 0
    op = 0
    litbuf = bytearray()

    def flush_literals():
        nonlocal op
        if not litbuf:
            return
        i = 0
        while i < len(litbuf):
            chunk = litbuf[i:i + MAX_LIT]
            out[op] = len(chunk) - 1
            op += 1
            out[op:op + len(chunk)] = chunk
            op += len(chunk)
            i += len(chunk)
        litbuf.clear()

    while ip < n - 2:
        hval = (inp[ip] << 8) | inp[ip + 1]
        hslot = ((hval >> (16 - HLOG)) - hval * 5) & (HSIZE - 1)
        ref = htab[hslot]
        htab[hslot] = ip

        off = ip - ref - 1
        if (ref >= 0 and ref < ip and off < MAX_OFF and ip + 4 < n
                and inp[ref] == inp[ip]
                and inp[ref + 1] == inp[ip + 1]
                and inp[ref + 2] == inp[ip + 2]
                and inp[ref + 3] == inp[ip + 3]):

            flush_literals()

            rem = (n - 2) - (ip + 3)
            if rem > MAX_REF - 3:
                rem = MAX_REF - 3
            total = 3
            r = ref + 3
            p = ip + 3
            while rem and p < n and inp[r] == inp[p]:
                r += 1
                p += 1
                rem -= 1
                total += 1

            enc_len = total - 2
            if enc_len < 7:
                out[op] = (off >> 8) + (enc_len << 5)
                op += 1
            else:
                out[op] = (off >> 8) + (7 << 5)
                op += 1
                out[op] = enc_len - 7
                op += 1
            out[op] = off & 0xFF
            op += 1

            ip += total
            if ip < n - 2:
                h = ip - 1
                hv = (inp[h] << 8) | inp[h + 1]
                htab[((hv >> (16 - HLOG)) - hv * 5) & (HSIZE - 1)] = h
                h = ip
                hv = (inp[h] << 8) | inp[h + 1]
                htab[((hv >> (16 - HLOG)) - hv * 5) & (HSIZE - 1)] = h
            continue

        litbuf.append(inp[ip])
        if len(litbuf) == MAX_LIT:
            flush_literals()
        ip += 1

    while ip < n:
        litbuf.append(inp[ip])
        if len(litbuf) == MAX_LIT:
            flush_literals()
        ip += 1
    flush_literals()

    return bytes(out[:op])


def decrypt(raw):
    return lzf_decompress(keyencode(raw))


def encrypt(text_bytes):
    return keyencode(lzf_compress(text_bytes))


def cmd_decrypt(args):
    src = Path(args.indir)
    dst = Path(args.outdir)
    dst.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    for p in sorted(src.iterdir()):
        if not p.is_file():
            continue
        try:
            (dst / p.name).write_bytes(decrypt(p.read_bytes()))
            ok += 1
        except Exception as e:
            fail += 1
            print(f"FAIL {p.name}: {e}", file=sys.stderr)
    print(f"decrypted {ok}/{ok+fail}")


def cmd_encrypt(args):
    src = Path(args.indir)
    dst = Path(args.outdir)
    dst.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    for p in sorted(src.iterdir()):
        if not p.is_file():
            continue
        try:
            (dst / p.name).write_bytes(encrypt(p.read_bytes()))
            ok += 1
        except Exception as e:
            fail += 1
            print(f"FAIL {p.name}: {e}", file=sys.stderr)
    print(f"encrypted {ok}/{ok+fail}")


SELITEM_RE = re.compile(r'^(SELITEM\s+)"(.*?)"(.*)$')
TF_RE = re.compile(r'^(TF\s+[-\d]+\s+[-\d]+\s+)"(.*)"\r?$')


def iter_text(lines):
    """Yield (line_index, kind, text) for translatable lines.

    kind: 'colon'  -> ":TEXT"
          'selitem'-> 'SELITEM "TEXT" label'
          'tf'     -> 'TF x y "TEXT"'
    """
    for i, line in enumerate(lines):
        if line.startswith(":"):
            yield i, "colon", line[1:]
            continue
        m = SELITEM_RE.match(line)
        if m:
            yield i, "selitem", m.group(2)
            continue
        m = TF_RE.match(line)
        if m:
            yield i, "tf", m.group(2)


def cmd_extract(args):
    """Extract translatable text units to JSONL: {file, idx, kind, en}."""
    import json

    src = Path(args.indir)
    units = []
    for p in sorted(src.iterdir()):
        if not p.is_file():
            continue
        text = p.read_bytes().decode("utf-8-sig", errors="replace")
        lines = text.split("\n")
        for i, kind, src_text in iter_text(lines):
            units.append({"file": p.name, "idx": i, "kind": kind,
                          "en": src_text.rstrip("\r")})
    out = Path(args.outfile)
    with out.open("w", encoding="utf-8") as f:
        for u in units:
            f.write(json.dumps(u, ensure_ascii=False) + "\n")
    print(f"extracted {len(units)} text units -> {out}")


def cmd_insert(args):
    """Insert translations from JSONL back into script files."""
    import json

    src = Path(args.indir)
    dst = Path(args.outdir)
    dst.mkdir(parents=True, exist_ok=True)
    by_file = {}
    with open(args.jsonl, encoding="utf-8") as f:
        for line in f:
            u = json.loads(line)
            by_file.setdefault(u["file"], {})[u["idx"]] = u
    n = 0
    for p in sorted(src.iterdir()):
        if not p.is_file():
            continue
        text = p.read_bytes().decode("utf-8-sig", errors="replace")
        lines = text.split("\n")
        repl = by_file.get(p.name, {})
        for idx, rec in repl.items():
            line = lines[idx]
            kind = rec.get("kind", "colon")
            es = rec["es"]
            cr = "\r" if line.endswith("\r") else ""
            if kind == "colon":
                assert line.startswith(":"), f"{p.name}:{idx} not a ':' line: {line!r}"
                new = ":" + es + cr
            elif kind == "selitem":
                m = SELITEM_RE.match(line)
                assert m, f"{p.name}:{idx} not a SELITEM line: {line!r}"
                new = m.group(1) + '"' + es + '"' + m.group(3)
            elif kind == "tf":
                m = TF_RE.match(line.rstrip("\r"))
                assert m, f"{p.name}:{idx} not a TF line: {line!r}"
                new = m.group(1) + '"' + es + '"' + cr
            else:
                raise ValueError(f"unknown kind {kind!r}")
            lines[idx] = new
            n += 1
        # re-add BOM if original had it
        raw = p.read_bytes()
        has_bom = raw.startswith(b"\xef\xbb\xbf")
        out_text = "\n".join(lines)
        data = out_text.encode("utf-8")
        if has_bom:
            data = b"\xef\xbb\xbf" + data
        (dst / p.name).write_bytes(data)
    print(f"inserted {n} translations into {len(by_file)} files -> {dst}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("dec", help="decrypt+decompress a dir of scripts")
    d.add_argument("indir")
    d.add_argument("outdir")
    d.set_defaults(func=cmd_decrypt)

    e = sub.add_parser("enc", help="compress+encrypt a dir of scripts")
    e.add_argument("indir")
    e.add_argument("outdir")
    e.set_defaults(func=cmd_encrypt)

    x = sub.add_parser("extract", help="extract dialogue to JSONL")
    x.add_argument("indir")
    x.add_argument("outfile")
    x.set_defaults(func=cmd_extract)

    i = sub.add_parser("insert", help="insert translations from JSONL")
    i.add_argument("indir")
    i.add_argument("jsonl")
    i.add_argument("outdir")
    i.set_defaults(func=cmd_insert)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
