#!/usr/bin/env python3
"""Live training/scoring session for apps/voice_dsp.

    pixi run live                 # prompts: single words, quick pairs and sentences
    pixi run live --mode sentences

The tool shows what to say, the board captures each word it hears and sends the window back with its
prediction. Words are labelled from the prompt ("switch on blue" = other, on, blue), scored live, and
saved to dataset_live/<label>/ so `pixi run train-export` can learn from them. Fillers (led, switch,
please, ...) are saved as class `other`. Ctrl-C ends the session and prints the summary.
"""
import argparse, glob, os, random, re, sys, time, wave
from collections import Counter, defaultdict

import numpy as np
import serial

N = 42 * 256
MAGIC = bytes([0xA5, 0x5A, 0xA5, 0x5A])
KEYWORDS = {"green", "blue", "on", "off"}
WORDS = ["green", "blue", "on", "off", "led", "light", "switch", "turn", "the", "please"]
PAIRS = ["blue on", "blue off", "green on", "green off", "on blue", "off blue", "on green", "off green"]
SENTENCES = ["blue led on", "blue led off", "green led on", "green led off", "blue light on", "green light off",
             "switch on blue", "switch off blue", "switch on green", "switch off green",
             "please blue on", "please green off", "turn the blue led on", "turn the green led off",
             "turn on the blue led", "turn off the green led"]
label_of = lambda tok: tok if tok in KEYWORDS else "other"


def class_names():
    text = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "apps", "voice_dsp", "model_params.h")).read()
    return re.findall(r'"(\w+)"', re.search(r"kClassNames\[[^\]]*\]\s*=\s*\{([^}]*)\}", text).group(1))


class Link:
    def __init__(self, port):
        port = port or (sorted(glob.glob("/dev/cu.usbmodem*")) or [None])[0]
        if not port:
            sys.exit("No /dev/cu.usbmodem* found - is the board plugged in?")
        self.ser = serial.Serial(port, 115200, timeout=0.05)
        self.ser.dtr = True
        self.buf = b""
        time.sleep(1.0)
        self.ser.write(b"S")                                   # stream mode: raw windows instead of text

    def window(self, timeout):
        """Next (kept_frames, class_index, probability, samples) from the board, or None after `timeout` s."""
        end = time.time() + timeout
        need = 8 + N * 2
        while time.time() < end:
            self.buf += self.ser.read(self.ser.in_waiting or 1)
            i = self.buf.find(MAGIC)
            if i >= 0 and len(self.buf) >= i + need:
                h = self.buf[i + 4:i + 8]
                x = np.frombuffer(self.buf[i + 8:i + need], dtype="<i2").copy()
                self.buf = self.buf[i + need:]
                return h[0], h[1], h[2] / 255.0, x
            if i < 0 and len(self.buf) > 3:
                self.buf = self.buf[-3:]                       # drop text/noise, keep a possible partial magic
        return None

    def drain(self, seconds=0.4):
        while self.window(seconds) is not None:
            pass

    def close(self):
        try:
            self.ser.write(b"T")
        finally:
            self.ser.close()


def save(path, x):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(x.astype("<i2").tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--mode", choices=["words", "pairs", "sentences", "mix"], default="mix")
    ap.add_argument("--out", default="dataset_live")
    ap.add_argument("--rounds", type=int, default=0, help="stop after this many prompts (default: until Ctrl-C)")
    args = ap.parse_args()

    names = class_names()
    pool = {"words": WORDS, "pairs": PAIRS, "sentences": SENTENCES,
            "mix": WORDS[:4] * 2 + WORDS[4:] + PAIRS * 2 + SENTENCES * 2}[args.mode]
    link = Link(args.port)
    conf = defaultdict(Counter)                               # true label -> predicted name -> count
    seg = defaultdict(lambda: [0, 0])                         # words in prompt -> [segmented right, total]
    saved = Counter()
    last = None
    n = 0
    print(f"Board classes: {names}.  Say each prompt at a natural pace; Ctrl-C to finish.\n")
    try:
        while not args.rounds or n < args.rounds:
            text = random.choice([p for p in pool if p != last]); last = text
            toks = text.split(); n += 1
            link.drain(0.3)
            print(f"[{n}] say:  {text}")
            first = link.window(30)
            if first is None:
                print("     (nothing heard, skipping)"); continue
            wins = [first]
            while (w := link.window(1.6)) is not None:
                wins.append(w)
            ok = len(wins) == len(toks)
            seg[len(toks)][1] += 1; seg[len(toks)][0] += ok
            if not ok:
                heard = ", ".join(f"{names[c]} {p:.2f}" for _, c, p, _ in wins)
                print(f"     board captured {len(wins)} word(s), expected {len(toks)}: {heard}  -> not saved")
                continue
            parts = []
            for tok, (kept, c, p, x) in zip(toks, wins):
                lab = label_of(tok); pred = names[c]
                conf[lab][pred] += 1
                save(f"{args.out}/{lab}/{lab}_{int(time.time() * 1000)}.wav", x); saved[lab] += 1
                mark = "ok" if pred == lab else ("-" if lab == "other" and "other" not in names else "WRONG")
                parts.append(f"{tok}->{pred} {p:.2f} {mark}")
            print("     " + " | ".join(parts))
    except KeyboardInterrupt:
        print()
    finally:
        link.close()

    print("\n=== session summary ===")
    print("windows saved:", dict(saved))
    print("segmentation (prompt length -> board captured the right number of words):")
    for k in sorted(seg):
        r, t = seg[k]; print(f"   {k} word(s): {r}/{t}")
    labs = sorted(conf)
    if labs:
        print("\nper-word accuracy of the board's prediction (rows = what you said):")
        cols = sorted({p for c in conf.values() for p in c} | set(names))
        print("          " + " ".join(f"{c:>6s}" for c in cols) + "   correct")
        for lab in labs:
            tot = sum(conf[lab].values())
            print(f"{lab:>9s} " + " ".join(f"{conf[lab][c]:6d}" for c in cols) + f"   {conf[lab][lab]}/{tot}")


if __name__ == "__main__":
    main()
