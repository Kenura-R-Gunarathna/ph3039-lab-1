"""Feature extraction for the word classifier (shared by the notebooks and the firmware port).

A clip is 1 s of 16 kHz int16 audio. Frames are 16 ms (256 samples, no overlap); a frame is "active"
when its energy is more than 10 dB above the quiet floor (20th-percentile frame energy).

The mic output has a start-up artifact: for ~0.3-1 s after the mic starts the DC level swings by hundreds of
counts and the first ~3 frames are noisy. Every clip in dataset/ was recorded in that period, so
  * only frames SKIP_FRAMES.. of a recorded clip are used (WINDOW_FRAMES of them), and
  * zcr / crest are computed per frame with each frame's own mean removed, so a slow DC drift cannot affect them.
The firmware classifies a window of WINDOW_FRAMES frames around a detected word, with the same features.
"""
import glob, os, wave

import numpy as np
from scipy import signal

FS = 16000
SKIP_FRAMES = 20          # skip the mic start-up part of a recorded clip
WINDOW_FRAMES = 42        # frames used per clip (672 ms); must equal VF_FRAMES in common/voice_features.h
BASE_NAMES = ["dur", "span", "peak_db", "b0", "b1", "b2", "b3", "cent", "hipos", "zcr", "crest"]
# temporal features: the active frames are split into 3 consecutive parts (start / middle / end of the word)
TEMPORAL_NAMES = [f"p{i}_{n}" for i in (1, 2, 3) for n in ("b0", "b1", "b2", "b3", "zcr")] + [f"p{i}_lvl" for i in (1, 2, 3)]
FEATURE_NAMES = BASE_NAMES + TEMPORAL_NAMES      # 11 + 18 = 29
BANDS = [(100, 500), (500, 1500), (1500, 3000), (3000, 8000)]


def extract(x):
    """Return the 29 features (order = FEATURE_NAMES) for one window of samples."""
    x = np.asarray(x, dtype=float)
    fr = x[:len(x) // 256 * 256].reshape(-1, 256)
    fr = fr - fr.mean(1, keepdims=True)                     # each frame with its own DC removed
    f, _, S = signal.spectrogram(x, FS, nperseg=256, noverlap=0)
    db = 10 * np.log10(S.sum(0) + 1e-9)
    floor = np.percentile(db, 20)
    act = db > floor + 10
    if act.sum() == 0:
        act[np.argmax(db)] = True
    idx = np.where(act)[0]
    Sa = S[:, act].sum(1)
    tot = Sa.sum() + 1e-9
    band = lambda lo, hi: Sa[(f >= lo) & (f < hi)].sum() / tot
    hi = S[f >= 3000].sum(0)
    span = max(idx[-1] - idx[0], 1)
    zc = (np.abs(np.diff(np.sign(fr), axis=1)) > 0).mean(1)           # per-frame zero-crossing rate
    parts = np.array_split(idx, 3) if len(idx) >= 3 else [idx, idx, idx]
    temporal = []
    for part in parts:                                                # start / middle / end of the word
        Sp = S[:, part].sum(1)
        tp = Sp.sum() + 1e-9
        temporal += [Sp[(f >= lo) & (f < hi_)].sum() / tp for lo, hi_ in BANDS] + [zc[part].mean()]
    temporal += [db[part].mean() - db.max() for part in parts]
    return [act.sum() * 0.016,                              # dur: active time (s)
            (idx[-1] - idx[0] + 1) * 0.016,                 # span: first to last active frame (s)
            db.max() - floor,                               # peak_db: loudest frame above floor (dB)
            *[band(lo, hi_) for lo, hi_ in BANDS],          # b0..b3: share of active energy per band
            (f * Sa).sum() / tot,                           # cent: spectral centroid (Hz)
            (np.argmax(hi * act) - idx[0]) / span,          # hipos: where the >3 kHz peak falls (0..1)
            np.mean(np.abs(np.diff(np.sign(fr), axis=1)) > 0),   # zcr: zero-crossing rate, per-frame DC removed
            np.abs(fr).max() / (np.sqrt(np.mean(fr ** 2)) + 1e-9),   # crest: peak / RMS, per-frame DC removed
            *temporal]                                      # 18 temporal features (see TEMPORAL_NAMES)


# --- mirror of the firmware capture in apps/voice_dsp/main.cpp (keep the constants in sync) ---
PRE, PAD, TRIG_RMS, TRIG_FRAMES, END_RMS, END_QUIET, MIN_WORD, TAIL = 10, 7, 300.0, 2, 120.0, 4, 5, 3


def board_window(x):
    """Build the 42-frame window the firmware would classify from a recorded clip, or None if the onset
    detector would never fire. Onset: frame RMS (DC removed) above TRIG_RMS for TRIG_FRAMES frames; the window is
    10 pre-roll frames + the word until it has been quiet for END_QUIET frames, padded with quiet pre-roll frames."""
    fr = np.asarray(x[:62 * 256], dtype=float).reshape(62, 256)
    rms = np.sqrt(np.mean((fr - fr.mean(1, keepdims=True)) ** 2, axis=1))
    hot = 0
    for t in range(PRE - 1, len(fr)):
        hot = hot + 1 if rms[t] > TRIG_RMS else 0
        if hot >= TRIG_FRAMES:
            win, quiet, kept = list(fr[t - PRE + 1:t + 1]), 0, None
            for u in range(t + 1, len(fr)):
                win.append(fr[u])
                quiet = quiet + 1 if rms[u] < END_RMS else 0
                if quiet >= END_QUIET and len(win) >= PRE + MIN_WORD:
                    kept = len(win) - quiet + TAIL
                    break
                if len(win) == WINDOW_FRAMES:
                    kept = WINDOW_FRAMES
                    break
            win = win[:kept if kept is not None else len(win)]
            k = 0
            while len(win) < WINDOW_FRAMES:                       # pad with quiet background from the pre-roll
                win.append(win[k % PAD]); k += 1
            return np.array(win[:WINDOW_FRAMES]).reshape(-1)
    return None


def read_wav(path):
    with wave.open(path) as w:
        assert w.getframerate() == FS and w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")


def load_dataset(root="dataset", classes=None, mode="board"):
    """Return X (n, 29), y (labels), paths for every clip in root/<label>/*.wav (folders starting with _ skipped).
    mode="board": the window the firmware would build (clips where the onset detector never fires are dropped,
                  e.g. most silent `noise` clips) - train as you deploy.
    mode="fixed": frames SKIP_FRAMES..SKIP_FRAMES+WINDOW_FRAMES of each clip (skips the mic start-up part).
    mode="raw":   each WAV already is a window captured by the board (tools/live_session.py), used as is.
    """
    labels = classes or sorted(d for d in os.listdir(root)
                               if os.path.isdir(f"{root}/{d}") and not d.startswith("_"))
    X, y, paths = [], [], []
    for lab in labels:
        for p in sorted(glob.glob(f"{root}/{lab}/*.wav")):
            x = read_wav(p)
            if mode == "board":
                x = board_window(x)
            elif mode == "fixed":
                x = x[SKIP_FRAMES * 256:(SKIP_FRAMES + WINDOW_FRAMES) * 256]
            elif len(x) != WINDOW_FRAMES * 256:
                raise ValueError(f"{p}: expected a {WINDOW_FRAMES}-frame window")
            if x is None:
                continue
            X.append(extract(x))
            y.append(lab)
            paths.append(p)
    return np.array(X), np.array(y), paths
