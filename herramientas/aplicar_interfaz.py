#!/usr/bin/env python3
"""Aplica la traduccion de la interfaz (menu) al sharedassets0.assets.

Este script NO distribuye ningun asset original del juego: parte de tu copia
legitima y aplica un parche delta (interfaz/menu_ui.delta) que solo contiene los
pixeles de las etiquetas traducidas.

Uso:
    python3 aplicar_interfaz.py <sharedassets0.assets> <sharedassets0.es.assets>

Requiere UnityPy (pip install UnityPy).
"""
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
DELTA = HERE.parent / "interfaz" / "menu_ui.delta"


def load_delta(path):
    payload = zlib.decompress(path.read_bytes())
    (hjson_len,) = struct.unpack("<I", payload[:4])
    header = json.loads(payload[4:4 + hjson_len])
    blobs = payload[4 + hjson_len:]
    return header, blobs


def main(bundle_in, bundle_out):
    import UnityPy

    bundle_in = Path(bundle_in)
    bundle_out = Path(bundle_out)
    if not bundle_in.is_file():
        sys.exit(f"No existe: {bundle_in}")
    if not DELTA.is_file():
        sys.exit(f"Falta el parche: {DELTA}")

    header, blobs = load_delta(DELTA)
    wanted = {t["name"]: t for t in header["textures"]}

    env = UnityPy.load(str(bundle_in))
    done = {}
    for obj in env.objects:
        if obj.type.name != "Texture2D":
            continue
        d = obj.read()
        name = getattr(d, "m_Name", "")
        spec = wanted.get(name)
        if not spec:
            continue

        raw = obj.get_raw_data()
        old = d.image_data

        md5_old = hashlib.md5(old).hexdigest()
        if len(old) != spec["size"] or md5_old != spec["md5_orig"]:
            sys.exit(
                f"{name}: los datos de textura no coinciden con los esperados.\n"
                f"  esperado size={spec['size']} md5={spec['md5_orig']}\n"
                f"  obtenido size={len(old)} md5={md5_old}\n"
                "  Tu sharedassets0.assets no es la version soportada."
            )

        new = bytearray(old)
        off = spec["blob_off"]
        for s, e in spec["ranges"]:
            n = e - s
            new[s:e] = blobs[off:off + n]
            off += n
        new = bytes(new)

        if hashlib.md5(new).hexdigest() != spec["md5_patched"]:
            sys.exit(f"{name}: el parche aplicado no da el resultado esperado.")

        idx = raw.find(old)
        if idx < 0:
            sys.exit(f"{name}: no se encontro image_data en el recurso.")
        obj.set_raw_data(raw[:idx] + new + raw[idx + len(old):])
        done[name] = spec["size"]

    missing = set(wanted) - set(done)
    if missing:
        sys.exit(f"No se encontraron las texturas: {', '.join(sorted(missing))}")

    out = env.files[str(bundle_in)].save()
    bundle_out.write_bytes(out)
    print(f"Texturas parcheadas: {', '.join(sorted(done))}")
    print(f"\nListo: {bundle_out}")
    print("Copialo sobre main_Data/sharedassets0.assets de tu instalacion.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
