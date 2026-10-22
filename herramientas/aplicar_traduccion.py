#!/usr/bin/env python3
"""Aplica la traducción al español al script.pac ORIGINAL del juego.

Este script NO distribuye el guion original: parte de tu copia legítima del
juego y sustituye las líneas por sus traducciones (traducciones/es.json).

Uso:
    python3 aplicar_traduccion.py <script.pac original> <script.pac.salida>

Requiere las herramientas cartagra_tool.py y mgpk.py (mismo directorio).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / "cartagra_tool.py"
MGPK = HERE / "mgpk.py"
TRAD = HERE.parent / "traducciones" / "es.json"


def run(*args):
    print("+", " ".join(str(a) for a in args))
    subprocess.run([sys.executable, *map(str, args)], check=True)


def split_keep_eol(text):
    """Divide conservando los finales de línea (\\r\\n, \\n o \\r)."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        j = i
        while j < n and text[j] not in "\r\n":
            j += 1
        line = text[i:j]
        eol = ""
        if j < n:
            if text[j] == "\r" and j + 1 < n and text[j + 1] == "\n":
                eol = "\r\n"; j += 2
            else:
                eol = text[j]; j += 1
        out.append((line, eol))
        i = j
    return out


def main(pac_in, pac_out):
    pac_in = Path(pac_in)
    pac_out = Path(pac_out)
    if not pac_in.is_file():
        sys.exit(f"No existe: {pac_in}")

    trad = json.loads(TRAD.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        extracted = tmp / "extracted"
        raw = tmp / "raw"
        txt = tmp / "txt"
        enc = tmp / "enc"

        # 1) extraer los .txt cifrados del script.pac y descifrarlos
        run(MGPK, "x", pac_in, extracted)
        run(TOOL, "dec", extracted, raw)

        # 2) aplicar traducciones por (archivo, línea) preservando EOL y BOM
        txt.mkdir()
        applied = 0
        for name in sorted(p.name for p in raw.iterdir() if p.is_file()):
            src = raw / name
            data = src.read_bytes()
            bom = b""
            if data[:3] == b"\xef\xbb\xbf":
                bom = data[:3]
                data = data[3:]
            text = data.decode("utf-8", errors="surrogateescape")
            parts = split_keep_eol(text)
            changes = trad.get(name)
            if changes:
                for idx_str, new in changes.items():
                    i = int(idx_str)
                    if i < len(parts):
                        parts[i] = (new, parts[i][1])
                        applied += 1
            rebuilt = "".join(line + eol for line, eol in parts)
            (txt / name).write_bytes(bom + rebuilt.encode("utf-8", errors="surrogateescape"))
        print(f"líneas traducidas aplicadas: {applied}")

        # 3) cifrar y reempaquetar
        run(TOOL, "enc", txt, enc)
        run(MGPK, "r", pac_in, pac_out, enc)

    print(f"\nListo: {pac_out}")
    print("Cópialo sobre GameData/script.pac de tu instalación del juego.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
