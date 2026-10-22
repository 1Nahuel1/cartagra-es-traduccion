import UnityPy, pathlib, shutil, sys

SRC = pathlib.Path('/mnt/disco_externo/cartagra_es/extracted/app/main_Data/sharedassets0.assets')
ART = pathlib.Path('/tmp/opencode/art')
PATCHED = {
    'MainUI': 'MainUI_patched_full.png',
    'SystemMenu': 'SystemMenu_patched.png',
    'SaveLoad': 'SaveLoad_patched.png',
    'ConfigScreen': 'ConfigScreen_patched.png',
}

def patch_texture(obj, png_path):
    d = obj.read()
    raw = obj.get_raw_data()
    old = d.image_data
    idx = raw.find(old)
    if idx < 0:
        raise RuntimeError(f'image_data not found in raw for {d.m_Name}')

    from PIL import Image
    newimg = Image.open(png_path).convert('RGBA')
    if newimg.size != d.image.size:
        raise RuntimeError(f'size mismatch {newimg.size} != {d.image.size} for {d.m_Name}')
    d.set_image(newimg)
    new = d.image_data
    patched = raw[:idx] + new + raw[idx+len(old):]
    obj.set_raw_data(patched)
    return len(old), len(new)

def main(dst):
    dst = pathlib.Path(dst)
    shutil.copy(SRC, dst)
    env = UnityPy.load(str(dst))
    done = {}
    for obj in env.objects:
        if obj.type.name != 'Texture2D':
            continue
        d = obj.read()
        name = getattr(d, 'm_Name', '')
        if name in PATCHED:
            lo, ln = patch_texture(obj, ART / PATCHED[name])
            done[name] = (lo, ln)
    out = env.files[str(dst)].save()
    dst.write_bytes(out)
    print('patched:', done)
    return dst

if __name__ == '__main__':
    dst = sys.argv[1] if len(sys.argv) > 1 else '/tmp/opencode/sharedassets0.patched.assets'
    main(dst)
