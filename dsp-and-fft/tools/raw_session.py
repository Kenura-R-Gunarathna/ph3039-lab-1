#!/usr/bin/env python3
"""Timed session that records the board's raw audio while you read prompts. No key presses needed.

    pixi run raw --minutes 5

Prompts appear on a timer (a few seconds each); just say them at a natural pace. Everything the mic hears
is saved to dataset_raw/session_<time>.wav (16 kHz mono) with session_<time>.json listing the prompt shown
at each moment, so word cutting and classifiers can be tuned offline without speaking again.
Ctrl-C ends the session early (what was recorded is still saved).
"""
import argparse, glob, json, os, random, sys, time, wave

import numpy as np
import serial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_session as ls

MAGIC = bytes([0xA5, 0x5A, 0xA5, 0x5A])
FRAME = 256
SECONDS = {1: 2.8, 2: 3.4, 3: 4.0, 4: 4.5, 5: 5.0}      # how long a prompt of N words stays on screen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--minutes", type=float, default=5.0)
    ap.add_argument("--mode", choices=["words", "pairs", "sentences", "mix"], default="mix")
    ap.add_argument("--out", default="dataset_raw")
    args = ap.parse_args()

    pool = {"words": ls.WORDS, "pairs": ls.PAIRS, "sentences": ls.SENTENCES,
            "mix": ls.WORDS[:4] * 2 + ls.WORDS[4:] + ls.PAIRS * 3 + ls.SENTENCES * 3}[args.mode]
    port = args.port or (sorted(glob.glob("/dev/cu.usbmodem*")) or [None])[0]
    if not port:
        sys.exit("No /dev/cu.usbmodem* found - is the board plugged in?")
    ser = serial.Serial(port, 115200, timeout=0.02)
    ser.dtr = True
    time.sleep(1.0)
    ser.write(b"R")                                           # raw mode

    buf = b""
    frames = {}                                               # seq -> samples
    first_seq, t_first = None, None
    prompts, last, n = [], None, 0
    t_end = time.time() + args.minutes * 60
    cur = None                                                # (text, tokens, shown_at_seq_time)
    print("Recording. Say each prompt when it appears (a new one shows every few seconds). Ctrl-C to stop.\n")
    try:
        while time.time() < t_end:
            buf += ser.read(ser.in_waiting or 1)
            while True:                                       # parse whole frames
                i = buf.find(MAGIC)
                if i < 0:
                    buf = buf[-3:]; break
                if len(buf) < i + 6 + FRAME * 2:
                    buf = buf[i:]; break
                seq = buf[i + 4] | (buf[i + 5] << 8)
                frames[seq if first_seq is None or seq >= first_seq else seq + 65536] = np.frombuffer(buf[i + 6:i + 6 + FRAME * 2], dtype="<i2").copy()
                if first_seq is None:
                    first_seq, t_first = seq, time.time()
                buf = buf[i + 6 + FRAME * 2:]
            now = time.time()
            if t_first is None:
                if now - (t_end - args.minutes * 60) > 5:
                    sys.exit("No audio from the board - flash apps/voice_dsp (make APP=voice_dsp flash) and retry.")
                continue
            if cur is None or now >= cur[3]:
                if cur is not None:
                    prompts.append({"text": cur[0], "tokens": cur[1], "start": cur[2], "end": (max(frames) - first_seq) * FRAME / 16000})
                text = random.choice([p for p in pool if p != last]); last = text; n += 1
                toks = text.split()
                cur = (text, toks, (max(frames) - first_seq) * FRAME / 16000, now + SECONDS.get(len(toks), 5.0))
                left = int((t_end - now) / 60 * 10) / 10
                print(f"[{n:3d}] say:  {text:28s}  ({left} min left)")
    except KeyboardInterrupt:
        print("\nstopping ...")
    finally:
        ser.write(b"T")
        time.sleep(0.3)
        ser.close()

    if cur is not None and frames:
        prompts.append({"text": cur[0], "tokens": cur[1], "start": cur[2], "end": (max(frames) - first_seq) * FRAME / 16000})
    if not frames:
        sys.exit("nothing recorded")
    last_seq = max(frames)
    total = last_seq - first_seq + 1
    missing = [s for s in range(first_seq, last_seq + 1) if s not in frames]
    audio = np.concatenate([frames.get(s, np.zeros(FRAME, dtype="<i2")) for s in range(first_seq, last_seq + 1)])
    os.makedirs(args.out, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    with wave.open(f"{args.out}/session_{stamp}.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(audio.tobytes())
    json.dump({"rate": 16000, "frame": FRAME, "prompts": prompts, "missing_frames": len(missing)},
              open(f"{args.out}/session_{stamp}.json", "w"), indent=1)
    print(f"\nsaved {args.out}/session_{stamp}.wav  ({total * FRAME / 16000:.0f} s, {len(prompts)} prompts, "
          f"{len(missing)} of {total} frames lost)")


if __name__ == "__main__":
    main()
