#!/usr/bin/env python3
"""Live test of apps/voice_cnn: read prompts on a timer, score what the board understands.

    pixi run cnn-test --minutes 4

Prompts appear every few seconds (say them naturally, like talking to a smart speaker). The board prints
"EV <word> <prob>" for each keyword it hears and "CMD <LED> <on|off>" for each LED command; this tool lines those up
with the prompts and reports:
  * keywords: correct / wrong word / missed / extra, over the whole session
  * commands: prompts with a colour AND on/off must give that LED command
Scoring does NOT depend on timing: the whole stream of keywords you were asked to say is aligned with the whole stream
the board reported (edit-distance alignment), so speaking a little early or late does not matter.
No audio is stored. Ctrl-C ends the session early and prints the summary.
"""
import argparse, glob, json, os, random, sys, time

import serial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_session as ls

SECONDS = {1: 2.8, 2: 3.4, 3: 4.0, 4: 4.5, 5: 5.0}
LAT_BEFORE, LAT_AFTER = 0.6, 0.6        # events belong to a prompt from (shown + 0.6 s) to (next shown + 0.6 s)


def expected_command(tokens):
    colour = [t for t in tokens if t in ("green", "blue")]
    action = [t for t in tokens if t in ("on", "off")]
    if len(colour) == 1 and len(action) == 1:
        return f"{colour[0].upper()} {action[0]}"
    return None


def collapse(seq):
    return [s for i, s in enumerate(seq) if i == 0 or s != seq[i - 1]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--minutes", type=float, default=4.0)
    ap.add_argument("--mode", choices=["words", "pairs", "sentences", "mix"], default="mix")
    ap.add_argument("--out", default="logs")
    args = ap.parse_args()

    pool = {"words": ls.WORDS, "pairs": ls.PAIRS, "sentences": ls.SENTENCES,
            "mix": ls.WORDS[:4] * 2 + ls.WORDS[4:] + ls.PAIRS * 3 + ls.SENTENCES * 3}[args.mode]
    port = args.port or (sorted(glob.glob("/dev/cu.usbmodem*")) or [None])[0]
    if not port:
        sys.exit("No /dev/cu.usbmodem* found - is the board plugged in?")
    ser = serial.Serial(port, 115200, timeout=0.05)
    ser.dtr = True
    time.sleep(1.0)
    ser.reset_input_buffer()

    events, cmds, shown = [], [], []            # (host time, word), (host time, "BLUE on"), (time shown, text)
    buf, last, n = b"", None, 0
    t0 = time.time(); t_end = t0 + args.minutes * 60
    cur_until = 0.0
    print("Say each prompt when it appears. Ctrl-C to stop.\n")
    try:
        while time.time() < t_end:
            buf += ser.read(ser.in_waiting or 1)
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                s = line.decode(errors="replace").strip()
                now = time.time()
                if s.startswith("EV "):
                    events.append((now, s.split()[1]))
                elif s.startswith("CMD "):
                    cmds.append((now, " ".join(s.split()[1:])))
            now = time.time()
            if now >= cur_until:
                text = random.choice([p for p in pool if p != last]); last = text; n += 1
                toks = text.split(); shown.append((now, text)); cur_until = now + SECONDS.get(len(toks), 5.0)
                print(f"[{n:3d}] say:  {text:28s} ({max(int((t_end - now) / 6) / 10, 0)} min left)")
    except KeyboardInterrupt:
        print("\nstopping ...")
    finally:
        ser.close()

    # ---- score (timing independent) ----
    end = time.time()
    done = [text for (t, text) in shown if t + SECONDS.get(len(text.split()), 5.0) <= end + 0.5]   # drop a prompt cut short by Ctrl-C
    summarize(done, [w for _, w in events], [c for _, c in cmds], args.out)


def align(a, b):
    """Edit-distance alignment of expected list a with heard list b -> [(op, i, j)], op in hit/sub/miss/extra."""
    n, m = len(a), len(b)
    D = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): D[i][0] = i
    for j in range(m + 1): D[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j] = min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    ops, i, j = [], n, m
    while i or j:
        if i and j and D[i][j] == D[i - 1][j - 1] + (a[i - 1] != b[j - 1]):
            ops.append(("hit" if a[i - 1] == b[j - 1] else "sub", i - 1, j - 1)); i -= 1; j -= 1
        elif i and D[i][j] == D[i - 1][j] + 1:
            ops.append(("miss", i - 1, None)); i -= 1
        else:
            ops.append(("extra", None, j - 1)); j -= 1
    return ops[::-1]


def summarize(texts, heard, cmds, outdir=None):
    toks = [t.split() for t in texts]
    want, owner = [], []                                        # expected keywords and the prompt each belongs to
    for k, t in enumerate(toks):
        for w in t:
            if w in ("green", "blue", "on", "off"):
                want.append(w); owner.append(k)
    ops = align(want, heard)
    per = [[] for _ in texts]; last = 0
    for op, i, j in ops:
        if i is not None: last = owner[i]
        if op == "hit":    per[owner[i]].append(want[i])
        elif op == "sub":  per[owner[i]].append(f"{want[i]}->{heard[j]}!")
        elif op == "miss": per[owner[i]].append(f"{want[i]} MISSED")
        else:              per[last].append(f"+{heard[j]} extra")
    for text, marks in zip(texts, per):
        bad = any(("!" in m or "MISSED" in m or "extra" in m) for m in marks)
        print(f"{'  ' if not bad else '✗ '}{text:28s} {', '.join(marks)}")
    cnt = {k: sum(o[0] == k for o in ops) for k in ("hit", "sub", "miss", "extra")}
    print(f"\n=== {len(texts)} prompts, {len(want)} keywords to hear, board reported {len(heard)} ===")
    print(f"keywords correct {cnt['hit']}/{len(want)} = {cnt['hit'] / max(len(want), 1) * 100:.0f} %   wrong word {cnt['sub']}   "
          f"missed {cnt['miss']}   extra {cnt['extra']}   keyword error rate {(cnt['sub'] + cnt['miss'] + cnt['extra']) / max(len(want), 1) * 100:.0f} %")
    cexp = [c for c in (expected_command(t) for t in toks) if c]
    if cexp:
        co = align(cexp, cmds); ch = sum(o[0] == "hit" for o in co)
        print(f"LED commands right {ch}/{len(cexp)} = {ch / len(cexp) * 100:.0f} %   wrong {sum(o[0] == 'sub' for o in co)}   "
              f"missed {sum(o[0] == 'miss' for o in co)}   extra {sum(o[0] == 'extra' for o in co)}   (executed {len(cmds)})")
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        json.dump(dict(prompts=texts, heard=heard, commands=cmds), open(f"{outdir}/cnn_session_{time.strftime('%Y%m%d_%H%M%S')}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
