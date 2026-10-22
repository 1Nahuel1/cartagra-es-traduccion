#!/usr/bin/env python3
"""Translate Cartagra dialogue units EN -> ES with Marian opus-mt-tc-big-en-es.

Protects proper nouns, Unity rich-text tags, `\\n` literals and `■■`.
Resumable: appends to per-worker JSONL, skips completed units.
Usage: translate_big.py units.jsonl out.jsonl [worker_idx total_workers]
"""
import json
import re
import sys
import time
from pathlib import Path

import torch
from transformers import MarianMTModel, MarianTokenizer

MODEL = "Helsinki-NLP/opus-mt-tc-big-en-es"

TOKEN_FMT = "ZXQ{}QXZ"
TOKEN_RE = re.compile(r"ZXQ(\d+)QXZ")

PERSON_NAMES = [
    "Akao", "Arishima", "Ayasaki", "Fukamizu", "Hatsune", "Hyo", "Ikuma",
    "Kaoru", "Kayo", "Kazuna", "Keiichiro", "Koyuki", "Kozuki", "Michio",
    "Nana", "Narahashi", "Otoha", "Rin", "Ryoko", "Sakura", "Senri", "Seri",
    "Shigusa", "Shugo", "Takako", "Takashiro", "Toji", "Tokiko", "Ujaku",
    "Yaginuma", "Yukishiro", "Yura", "Aoki", "Shu",
]
PLACES = ["Ueno", "Zushi", "Tokyo", "Aoimachi", "Kanda", "Benten",
          "Shinobazu", "Fukagawa", "Umedaya"]
HONORIFIC = r"(?:-(?:san|sama|chan|kun|sensei|dono))?"
NAME_RE = re.compile(
    r"\b(?:" + "|".join(sorted(map(re.escape, PERSON_NAMES + PLACES), key=len, reverse=True))
    + r")" + HONORIFIC + r"\b"
)
TAG_RE = re.compile(r"<[^>]+>")
NEWLINE_LITERAL = "\\n"
PLACEHOLDER = "\u25a0\u25a0"

QUOTES_OPEN = "\"'“‘"
QUOTES_CLOSE = "\"'”’"


class Protector:
    def __init__(self):
        self.map = {}
        self.rev = {}

    def _tok(self, value):
        if value not in self.map:
            tok = TOKEN_FMT.format(len(self.map))
            self.map[value] = tok
            self.rev[tok] = value
        return self.map[value]

    def protect(self, text):
        text = text.replace(PLACEHOLDER, " " + self._tok(PLACEHOLDER) + " ")
        text = text.replace(NEWLINE_LITERAL, " " + self._tok(NEWLINE_LITERAL) + " ")
        text = TAG_RE.sub(lambda m: " " + self._tok(m.group(0)) + " ", text)
        text = NAME_RE.sub(lambda m: self._tok(m.group(0)), text)
        return text

    def restore(self, text):
        text = TOKEN_RE.sub(lambda m: self.rev.get(m.group(0), m.group(0)), text)
        # collapse the padding spaces introduced around newline/tag tokens
        text = re.sub(r"\s*\\n\s*", lambda m: NEWLINE_LITERAL, text)
        text = re.sub(r"\s*(<[^>]+>)\s*", r"\1", text)
        text = re.sub(r"\s*" + re.escape(PLACEHOLDER) + r"\s*", lambda m: PLACEHOLDER, text)
        return text


END_PUNCT = ".!?…\"'”’"


def fix_quotes(src, dst):
    src = src.strip()
    dst = dst.strip()
    if not src or not dst:
        return dst
    if src[0] in QUOTES_OPEN:
        if dst[0] not in QUOTES_OPEN:
            dst = src[0] + dst
        elif dst[0] != src[0]:
            dst = src[0] + dst[1:]
    if src[-1] in QUOTES_CLOSE:
        # strip a duplicated trailing sentence punctuation before the quote
        if dst[-1] in END_PUNCT and dst[-1] not in QUOTES_CLOSE:
            if len(dst) >= 2 and dst[-2] in QUOTES_CLOSE:
                dst = dst[:-1]
        if dst[-1] not in QUOTES_CLOSE:
            dst = dst + src[-1]
        elif dst[-1] != src[-1]:
            dst = dst[:-1] + src[-1]
    return dst


def main():
    units_jsonl, out_jsonl = sys.argv[1], sys.argv[2]
    widx = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    wtotal = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    threads = int(sys.argv[5]) if len(sys.argv) > 5 else 3

    torch.set_num_threads(threads)
    tok = MarianTokenizer.from_pretrained(MODEL)
    model = MarianMTModel.from_pretrained(MODEL).eval()

    units = [json.loads(l) for l in Path(units_jsonl).open(encoding="utf-8")]
    if wtotal > 1:
        units = units[widx::wtotal]

    out_path = Path(out_jsonl)
    done = set()
    if out_path.exists():
        for l in out_path.open(encoding="utf-8"):
            try:
                u = json.loads(l)
                done.add(u["idx"])
            except Exception:
                pass
    todo = [u for u in units if u["idx"] not in done]
    print(f"worker {widx}: {len(todo)} todo / {len(units)}", file=sys.stderr, flush=True)

    # pre-encode protected text, bucket by length
    prepared = []
    for u in todo:
        prot = Protector()
        p = prot.protect(u["en"])
        ids = tok(p, truncation=True, max_length=250)["input_ids"]
        prepared.append((len(ids), u, prot, p, len(ids)))

    BATCH = 24
    t0 = time.time()
    fout = out_path.open("a", encoding="utf-8")
    prepared.sort(key=lambda x: x[0])
    n_done = 0
    for i in range(0, len(prepared), BATCH):
        chunk = prepared[i : i + BATCH]
        maxlen = chunk[-1][0]
        texts = [c[3] for c in chunk]
        b = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=256)
        max_new = min(256, int(maxlen * 2.0) + 16)
        with torch.inference_mode():
            out = model.generate(**b, max_new_tokens=max_new, num_beams=1)
        dec = tok.batch_decode(out, skip_special_tokens=True)
        for (_, u, prot, src, _), es in zip(chunk, dec):
            es = prot.restore(es.strip())
            if u.get("kind", "colon") == "colon":
                es = fix_quotes(u["en"], es)
            if not es.strip():
                es = u["en"]
            fout.write(json.dumps({"file": u["file"], "idx": u["idx"],
                                   "kind": u.get("kind", "colon"),
                                   "en": u["en"], "es": es}, ensure_ascii=False) + "\n")
        fout.flush()
        n_done += len(chunk)
        if n_done % (BATCH * 4) == 0:
            rate = n_done / max(time.time() - t0, 1e-6)
            print(f"w{widx} {n_done}/{len(prepared)} {rate:.1f}/s", file=sys.stderr, flush=True)
    fout.close()
    print(f"worker {widx} done", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
