#!/usr/bin/env python3
"""Menu-driven voice dataset tool for the XIAO nRF52840 Sense (firmware: apps/audio_capture).

    pixi run record            (or: python tools/dataset_cli.py [--port /dev/cu.usbmodemXXXX])

Layout:  dataset/<word>/<word>_<timestamp>.wav     16 kHz, mono, 16-bit, 1 s clips
         dataset/noise/...                          background noise (also the "noise" class)
         dataset/_trash/                            deleted words/clips land here (reversible)
         dataset_aug/<word>/...                     built by menu 5: originals + noise-mixed copies
"""
import argparse, glob, os, random, shutil, subprocess, sys, time, wave
import numpy as np
import serial

RATE, CLIP = 16000, 16000
MAGIC = bytes([0xA5, 0x5A, 0xA5, 0x5A])
DATA, AUG, TRASH = "dataset", "dataset_aug", "dataset/_trash"
NOISE = "noise"                                   # reserved label


# ---------- board ----------
class Board:
    def __init__(self, port):
        self.port, self.ser = port, None

    def connect(self):
        port = self.port or (sorted(glob.glob("/dev/cu.usbmodem*")) or [None])[0]
        if not port:
            return False
        try:
            self.ser = serial.Serial(port, 115200, timeout=3)
            time.sleep(2)                          # opening the port can reboot the board
            self.port = port
            return True
        except serial.SerialException as e:
            print("  cannot open", port, "-", e)
            return False

    def _once(self):
        self.ser.reset_input_buffer()
        self.ser.write(b"g")
        if not self.ser.read_until(MAGIC).endswith(MAGIC):
            raise TimeoutError("no header from board (is apps/audio_capture flashed?)")
        raw = self.ser.read(CLIP * 2)
        if len(raw) != CLIP * 2:
            raise TimeoutError(f"short clip: {len(raw)} of {CLIP * 2} bytes")
        return np.frombuffer(raw, dtype="<i2")

    def record(self):
        if self.ser is None and not self.connect():
            raise TimeoutError("board not found - plug it in (or pass --port)")
        try:
            try:
                return self._once()
            except TimeoutError:
                return self._once()                # one retry (first request after connecting)
        except serial.SerialException:
            self.ser = None
            raise TimeoutError("lost the board - reconnect it and try again")


# ---------- files ----------
def read_wav(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")

def write_wav(path, x):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(np.asarray(x, dtype="<i2").tobytes())

def clips_of(label):
    return sorted(glob.glob(f"{DATA}/{label}/*.wav"))

def labels():
    found = [os.path.basename(d.rstrip("/")) for d in glob.glob(f"{DATA}/*/")]
    return sorted(l for l in found if not l.startswith("_") and l != NOISE)

def clean_name(s):
    s = "".join(ch for ch in s.strip().lower().replace(" ", "_") if ch.isalnum() or ch == "_")
    return s.lstrip("_")

def rename_label(old, new):
    os.rename(f"{DATA}/{old}", f"{DATA}/{new}")
    for p in glob.glob(f"{DATA}/{new}/{old}_*.wav"):
        os.rename(p, p.replace(f"/{old}_", f"/{new}_"))

def to_trash(path):
    os.makedirs(TRASH, exist_ok=True)
    dest = f"{TRASH}/{int(time.time())}_{os.path.basename(path.rstrip('/'))}"
    shutil.move(path, dest)
    return dest

def play(path):
    subprocess.run(["afplay", path])

def ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return "q"


# ---------- recording ----------
def level_note(x, speech=True):
    peak = int(np.abs(x).max())
    rms = float(np.std(x.astype(float)))
    note = "  (CLIPPING)" if peak > 32000 else "  (very quiet - closer/louder)" if speech and peak < 1500 else ""
    return f"peak={peak} rms={rms:.0f}{note}"

def record_loop(board, label, autoplay):
    last = None
    print(f"\nRecording '{label}'.  Enter = record   N = record N in a row   p = play last   "
          f"d = delete last   a = toggle autoplay   q = back")
    while True:
        n = len(clips_of(label))
        cmd = ask(f"[{label} #{n + 1}] > ").lower()
        if cmd == "q":
            return autoplay
        if cmd == "a":
            autoplay = not autoplay
            print("  autoplay", "on" if autoplay else "off")
        elif cmd == "p":
            if last and os.path.exists(last):
                play(last)
        elif cmd == "d":
            if last and os.path.exists(last):
                to_trash(last); print("  moved to trash:", last); last = None
        elif cmd == "" or cmd.isdigit():
            count = 1 if cmd == "" else min(int(cmd), 200)
            for k in range(count):
                if count > 1:
                    print(f"  clip {k + 1}/{count} ...")
                else:
                    print("  speak NOW ...")
                try:
                    x = board.record()
                except TimeoutError as e:
                    print("  error:", e); break
                last = f"{DATA}/{label}/{label}_{int(time.time() * 1000)}.wav"
                write_wav(last, x)
                print(f"  saved {os.path.basename(last)}  {level_note(x, label != NOISE)}")
                if autoplay and count == 1:
                    play(last)
        else:
            print("  ?")


# ---------- menus ----------
def pick_label(allow_new=True):
    ls = labels()
    for i, l in enumerate(ls, 1):
        print(f"  {i}) {l}  ({len(clips_of(l))} clips)")
    hint = "number, or type a new word to create it" if allow_new else "number"
    s = ask(f"Word ({hint}, blank = cancel): ")
    if not s or s == "q":
        return None
    if s.isdigit() and 1 <= int(s) <= len(ls):
        return ls[int(s) - 1]
    name = clean_name(s)
    if not allow_new or not name or name == NOISE:
        print("  not a valid word name"); return None
    if name not in ls:
        os.makedirs(f"{DATA}/{name}", exist_ok=True); print(f"  created '{name}'")
    return name

def menu_manage():
    while True:
        print("\n-- Manage words --")
        for l in labels():
            print(f"  {l}  ({len(clips_of(l))} clips)")
        print(f"  {NOISE}  ({len(clips_of(NOISE))} clips)  [reserved, background noise]")
        c = ask("c = create   r = rename   d = delete   q = back > ").lower()
        if c == "q":
            return
        if c == "c":
            name = clean_name(ask("New word: "))
            if not name or name == NOISE or name in labels():
                print("  invalid or already exists")
            else:
                os.makedirs(f"{DATA}/{name}"); print("  created", name)
        elif c in ("r", "d"):
            old = pick_label(allow_new=False)
            if not old:
                continue
            if c == "r":
                new = clean_name(ask(f"Rename '{old}' to: "))
                if not new or new == NOISE or new in labels():
                    print("  invalid or already exists"); continue
                rename_label(old, new)
                print(f"  renamed {old} -> {new}")
            elif ask(f"Delete '{old}' and its {len(clips_of(old))} clips? type the word to confirm: ") == old:
                print("  moved to", to_trash(f"{DATA}/{old}"))

def menu_review():
    label = pick_label(allow_new=False) or (NOISE if ask(f"Review '{NOISE}'? (y/n) ").lower() == "y" else None)
    if not label:
        return
    while True:
        files = clips_of(label)
        print(f"\n-- {label}: {len(files)} clips --")
        for i, p in enumerate(files, 1):
            x = read_wav(p)
            print(f"  {i:3d}) {os.path.basename(p)}  {level_note(x)}")
        c = ask("p N = play   d N = delete   q = back > ").lower().split()
        if not c or c[0] == "q":
            return
        if len(c) == 2 and c[1].isdigit() and 1 <= int(c[1]) <= len(files):
            f = files[int(c[1]) - 1]
            if c[0] == "p":
                play(f)
            elif c[0] == "d":
                to_trash(f); print("  moved to trash")

def mix(speech, noise, snr_db):
    s = speech.astype(float) - speech.mean()
    n = noise.astype(float) - noise.mean()
    gain = np.sqrt(np.mean(s ** 2) + 1e-9) / (np.sqrt(np.mean(n ** 2) + 1e-9) * 10 ** (snr_db / 20))
    return s + n * gain

def build_augmented(k):
    """Write dataset_aug/: every original clip plus k noise-mixed copies of each word clip.
    Returns the number of clips written, or None if there is no background noise yet."""
    pool = clips_of(NOISE)
    if not pool:
        return None
    rng = random.Random(0)
    shutil.rmtree(AUG, ignore_errors=True)
    total = 0
    for label in labels() + [NOISE]:
        for p in clips_of(label):
            x = read_wav(p)
            os.makedirs(f"{AUG}/{label}", exist_ok=True)
            shutil.copy(p, f"{AUG}/{label}/")
            total += 1
            if label == NOISE:
                continue
            for j in range(k):
                noise = read_wav(rng.choice(pool))
                shift = rng.randint(-1600, 1600)                       # +-100 ms
                y = np.roll(x, shift).astype(float)
                if shift > 0: y[:shift] = 0
                elif shift < 0: y[shift:] = 0
                y = mix(y, noise, rng.uniform(5, 20)) * rng.uniform(0.6, 1.4)
                base = os.path.basename(p)[:-4]
                write_wav(f"{AUG}/{label}/{base}_aug{j + 1}.wav", np.clip(y, -32768, 32767))
                total += 1
    return total

def menu_augment():
    if not clips_of(NOISE):
        print("  record some background noise first (menu 2)"); return
    try:
        k = int(ask("Noise-mixed copies per word clip [default 3]: ") or 3)
    except ValueError:
        k = 3
    total = build_augmented(k)
    print(f"  wrote {total} clips to {AUG}/  (originals + {k} noise-mixed copies each, SNR 5-20 dB, +-100 ms shift)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    args = ap.parse_args()
    os.makedirs(f"{DATA}/{NOISE}", exist_ok=True)
    board = Board(args.port)
    print("Connecting to board ...", "ok: " + board.port if board.connect() else "not found (will retry when recording)")
    autoplay = True
    while True:
        print(f"\n=== Voice dataset ===   board: {board.port or 'not connected'}")
        for l in labels():
            print(f"    {l}: {len(clips_of(l))} clips")
        print(f"    {NOISE}: {len(clips_of(NOISE))} clips")
        print("  1) Record a word      2) Record background noise      3) Manage words")
        print("  4) Review clips       5) Build augmented set           q) Quit")
        c = ask("> ").lower()
        if c == "1":
            label = pick_label()
            if label:
                autoplay = record_loop(board, label, autoplay)
        elif c == "2":
            print("\nRecord ordinary background (silence, fan, typing, TV, room talk) - NOT the keywords.")
            autoplay = record_loop(board, NOISE, autoplay)
        elif c == "3":
            menu_manage()
        elif c == "4":
            menu_review()
        elif c == "5":
            menu_augment()
        elif c == "q":
            return


if __name__ == "__main__":
    main()
