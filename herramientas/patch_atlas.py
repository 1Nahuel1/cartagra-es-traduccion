import sys
from PIL import Image, ImageDraw, ImageFont
import numpy as np

FONT = '/tmp/opencode/fonts/ttf/VeraMono-Bold.ttf'
TEXT_COLOR = (182, 241, 242, 255)

def load(path):
    return Image.open(path).convert('RGBA')

def erase_text(img, box, pad=2):
    """Fill the text box with the local background color (median of surrounding)."""
    x0, y0, x1, y1 = box
    X0, Y0 = max(0, x0 - pad - 3), max(0, y0 - pad - 3)
    X1, Y1 = min(img.width - 1, x1 + pad + 3), min(img.height - 1, y1 + pad + 3)
    a = np.array(img.crop((X0, Y0, X1 + 1, Y1 + 1))).astype(int)
    patch = a.reshape(-1, 4)
    br = patch[:, :3].sum(1) / 3
    al = patch[:, 3]
    bg = patch[(al > 128) & (br < 130)]
    if len(bg) == 0:
        bg = patch[al > 128]
    col = tuple(int(v) for v in np.median(bg, 0)[:3]) + (255,)
    d = ImageDraw.Draw(img)
    d.rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], fill=col)
    return col

def fit_font(draw, text, max_w, max_h, start=12):
    for size in range(start, 4, -1):
        f = ImageFont.truetype(FONT, size)
        bb = draw.textbbox((0, 0), text, font=f)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        if w <= max_w and h <= max_h:
            return f, bb
    f = ImageFont.truetype(FONT, 5)
    return f, draw.textbbox((0, 0), text, font=f)

def patch_label(img, box, new_text, color=TEXT_COLOR):
    x0, y0, x1, y1 = box
    erase_text(img, box)
    w, h = x1 - x0 + 1, y1 - y0 + 1
    d = ImageDraw.Draw(img)
    f, bb = fit_font(d, new_text, w + 6, h + 2)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    tx = x0 + (w - tw) // 2 - bb[0]
    ty = y0 + (h - th) // 2 - bb[1]
    d.text((tx, ty), new_text, font=f, fill=color)
    return f

if __name__ == '__main__':
    pass
