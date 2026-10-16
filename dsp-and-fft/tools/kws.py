"""Data + models for continuous keyword spotting with small 1D CNNs (PyTorch).

Input is a log-mel spectrogram, one column per 16 ms frame (32 mel bands), so a 1D convolution slides over TIME
with the mel bands as channels. Training sentences are synthesised from the isolated word recordings (exact word
times known); the real continuous sessions in dataset_raw/ are used only for testing.
"""
import copy, glob, json, os, sys, time, wave

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as Fn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import voice_features as vf

KW = ["blue", "green", "off", "on"]
CLASSES = ["bg"] + KW                      # window classifier outputs
NM, W = 32, 42                             # mel bands, window length in frames (0.67 s)
IGNORE = -1

FILL = ["led", "light", "switch", "turn", "the", "please"]
PAIRS = ["blue on", "blue off", "green on", "green off", "on blue", "off blue", "on green", "off green"]
SENT = ["blue led on", "blue led off", "green led on", "green led off", "blue light on", "green light off",
        "switch on blue", "switch off blue", "switch on green", "switch off green", "please blue on", "please green off",
        "turn the blue led on", "turn the green led off", "turn on the blue led", "turn off the green led"]
PROMPTS = PAIRS * 3 + SENT * 3 + KW * 2 + FILL

frames_of = lambda x: np.asarray(x[:len(x) // 256 * 256], dtype=float).reshape(-1, 256)
frame_rms = lambda fr: np.sqrt(np.mean((fr - fr.mean(1, keepdims=True)) ** 2, axis=1))


# ---------------------------------------------------------------- log-mel
def _mel_fb(nb=NM, lo=100, hi=7600, n=256, fs=16000):
    hz2m = lambda f: 2595 * np.log10(1 + f / 700)
    m2hz = lambda m: 700 * (10 ** (m / 2595) - 1)
    pts = m2hz(np.linspace(hz2m(lo), hz2m(hi), nb + 2))
    bins = np.fft.rfftfreq(n, 1 / fs)
    fb = np.zeros((nb, len(bins)))
    for i in range(nb):
        a, b, c = pts[i:i + 3]
        fb[i] = np.clip(np.minimum((bins - a) / (b - a), (c - bins) / (c - b)), 0, None)
    return fb


FB, HANN = _mel_fb(), np.hanning(256)


def logmel(fr):
    """(frames, 256) samples -> (frames, 32) log-mel in dB. Each frame has its own DC removed."""
    d = (fr - fr.mean(1, keepdims=True)) * HANN
    return (10 * np.log10(np.abs(np.fft.rfft(d, axis=1)) ** 2 @ FB.T + 1.0)).astype(np.float32)


# ---------------------------------------------------------------- word pool + synthetic sentences
def _core(fr, thr=150):
    r = frame_rms(fr)
    idx = np.where(r > thr)[0]
    return None if len(idx) == 0 else fr[max(idx[0] - 1, 0):idx[-1] + 2]


class Pool:
    def __init__(self, root="."):
        j = lambda *p: os.path.join(root, *p)
        self.words = {k: [] for k in KW + ["other"]}
        for k in KW:
            for p in sorted(glob.glob(j("dataset", k, "*.wav"))):
                c = _core(frames_of(vf.read_wav(p))[20:62])               # skip the mic start-up frames
                if c is not None and 6 <= len(c) <= 40:
                    self.words[k].append(c)
        live = j("dataset_live")
        for lab in (os.listdir(live) if os.path.isdir(live) else []):
            if lab.startswith("_"):
                continue
            for p in sorted(glob.glob(j("dataset_live", lab, "*.wav"))):
                c = _core(frames_of(vf.read_wav(p)))
                if c is not None and 6 <= len(c) <= 40:
                    self.words[lab if lab in self.words else "other"].append(c)
        for p in sorted(glob.glob(j("dataset", "noise", "*.wav"))):
            c = _core(frames_of(vf.read_wav(p))[20:62], 300)
            if c is not None and 3 <= len(c) <= 30:
                self.words["other"].append(c)
        self.bg = np.array([f for p in sorted(glob.glob(j("dataset", "noise", "*.wav")))
                            for f in frames_of(vf.read_wav(p))[25:] if frame_rms(f[None])[0] < 25])

    def background(self, rng, n):
        return list(self.bg[rng.integers(0, len(self.bg), n)])

    def sentence(self, rng):
        """-> (frames (T,256), spans [(a, b, cls)]) with cls in KW or 'other'."""
        text = PROMPTS[rng.integers(len(PROMPTS))]
        frames = self.background(rng, rng.integers(12, 35))
        spans = []
        for tok in text.split():
            cls = tok if tok in KW else "other"
            w = self.words[cls][rng.integers(len(self.words[cls]))] * np.exp(rng.uniform(np.log(0.35), np.log(2.0)))
            s = len(frames)
            frames += list(np.clip(w, -32768, 32767))
            spans.append((s, len(frames), cls))
            frames += self.background(rng, rng.integers(0, 8))
        frames += self.background(rng, rng.integers(15, 35))
        while len(frames) < W + 10:
            frames += self.background(rng, 1)
        return np.array(frames), spans


def frame_targets(T, spans):
    """Per-frame labels from word spans: window class (index into CLASSES, IGNORE near keyword edges),
    inside-a-word flag, and a soft word-onset target."""
    cls = np.zeros(T, dtype=np.int64)
    inside = np.zeros(T, dtype=np.float32)
    onset = np.zeros(T, dtype=np.float32)
    t = np.arange(T)
    for a, b, c in spans:
        inside[a:b] = 1
        onset = np.maximum(onset, np.exp(-0.5 * ((t - a) / 1.5) ** 2).astype(np.float32))
    for a, b, c in spans:
        if c in KW:
            cls[max(a - 8, 0):b + 8] = IGNORE                     # near a keyword: ambiguous
    for a, b, c in spans:
        if c in KW:
            cls[a + 3:b - 3] = CLASSES.index(c)
    return cls, inside, onset


# ---------------------------------------------------------------- models
def _block(i, o, k=3, stride=1, dil=1):
    return [nn.Conv1d(i, o, k, stride=stride, padding=dil * (k // 2), dilation=dil), nn.BatchNorm1d(o), nn.ReLU()]


class KwsCnn(nn.Module):
    """Window classifier: (B, 32, 42) log-mel -> 5 class logits. ~30 k weights."""
    def __init__(self, c1=32, c2=48, c3=64):
        super().__init__()
        self.net = nn.Sequential(*_block(NM, c1), *_block(c1, c2, stride=2), *_block(c2, c3, stride=2), *_block(c3, c3))
        self.fc = nn.Linear(2 * c3, len(CLASSES))

    def forward(self, x):
        h = self.net(x)
        return self.fc(torch.cat([h.mean(2), h.amax(2)], 1))


class Splitter(nn.Module):
    """Fully convolutional: (B, 32, T) -> (B, 2, T) logits [inside a word, word onset]. Receptive field 29 frames."""
    def __init__(self, c=32):
        super().__init__()
        self.net = nn.Sequential(*_block(NM, c, 5), *_block(c, c, 5, dil=2), *_block(c, c, 5, dil=4), nn.Conv1d(c, 2, 1))

    def forward(self, x):
        return self.net(x)


# ---------------------------------------------------------------- real session (test set)
def load_real(root="."):
    """Real continuous prompts with exactly one utterance: list of dict(text, want (keywords in order), region, ...)."""
    out = []
    for f in sorted(glob.glob(os.path.join(root, "dataset_raw", "session_*.wav"))):
        w = wave.open(f)
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float)
        P = json.load(open(f.replace(".wav", ".json")))["prompts"]
        fr = frames_of(x)
        n = len(fr)
        r = frame_rms(fr)
        utt, t = [], 0
        while t < n:
            if r[t] > 300:
                s = t
                while t < n and (r[t:t + 38] > 120).any():
                    t += 1
                utt.append((s, t))
            t += 1
        for p in P:
            a, b = p["start"] / 0.016, p["end"] / 0.016
            ins = [u for u in utt if a <= u[0] < b + 30]
            if len(ins) != 1:
                continue
            lo, hi = max(ins[0][0] - 25, 0), min(ins[0][1] + 30, n)
            out.append(dict(text=p["text"], tokens=p["text"].split(), want=[t_ for t_ in p["text"].split() if t_ in KW],
                            frames=fr[lo:hi]))
    return out


# ---------------------------------------------------------------- scoring helpers
def collapse(seq):
    return [s for i, s in enumerate(seq) if i == 0 or s != seq[i - 1]]


def lev(a, b):
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
    return d[len(b)]


def score(seqs):
    """seqs: [(got, want)] -> (exact %, keyword error rate %). Repeats of one keyword in a row count once."""
    ex = sum(collapse(g) == w for g, w in seqs)
    err = sum(lev(collapse(g), w) for g, w in seqs)
    return ex / len(seqs) * 100, err / max(sum(len(w) for _, w in seqs), 1) * 100


# ---------------------------------------------------------------- inference + decoding (same logic as the firmware)
STRIDE = 4            # the firmware runs the CNN every 4 frames (64 ms)
HOLD = 3              # windows a candidate must survive without a higher peak (= 12 frames)
THETA = 0.5


def probs(net, Ln, stride=STRIDE):
    """Class probabilities for every window (every `stride` frames) of a normalised log-mel matrix Ln (frames, 32)."""
    starts = list(range(0, len(Ln) - W + 1, stride))
    X = torch.from_numpy(np.stack([Ln[s:s + W].T for s in starts]).astype(np.float32))
    with torch.no_grad():
        return torch.softmax(net(X), 1).numpy()


def stream_decode(P, theta=THETA, hold=HOLD):
    """The decoder the firmware runs (common/kws_cnn.cpp::kwsDecode): a keyword peak above `theta` is reported once
    `hold` windows pass without a higher keyword peak; a lower peak inside that time is ignored."""
    events, cand = [], None
    for p in P:
        k = 1 + int(np.argmax(p[1:]))
        if p[k] >= theta and (cand is None or p[k] > cand[1]):
            cand = [k, p[k], 0]
        elif cand is not None:
            cand[2] += 1
        if cand is not None and cand[2] >= hold:
            events.append(CLASSES[cand[0]]); cand = None
    if cand is not None:
        events.append(CLASSES[cand[0]])
    return events


def align(logP, D=3):
    """Keyword positions t_1 < ... < t_m (>= D windows apart) maximising the summed log-probability (dynamic programming)."""
    T, m = logP.shape
    NEG = -1e9
    dp = np.full((m, T), NEG); bp = np.zeros((m, T), int); dp[0] = logP[:, 0]
    for j in range(1, m):
        best, arg = NEG, 0
        for t in range(T):
            if t - D >= 0 and dp[j - 1][t - D] > best:
                best, arg = dp[j - 1][t - D], t - D
            if best > NEG / 2:
                dp[j][t] = best + logP[t, j]; bp[j][t] = arg
    t = int(np.argmax(dp[m - 1])); pos = [t]
    for j in range(m - 1, 0, -1):
        t = bp[j][t]; pos.append(t)
    return pos[::-1]


# ---------------------------------------------------------------- training
class Trainer:
    """Synthetic sentences + real sessions, pre-training and fine-tuning of KwsCnn (used by tools/train_cnn.py and the notebook)."""
    PROBS = [0.30, 0.175, 0.175, 0.175, 0.175]          # class sampling in a training batch

    def __init__(self, models="models", seed=0, sentences=2500, fresh_norm=False, root="."):
        self.rng = np.random.default_rng(seed)
        torch.manual_seed(seed)
        self.models = models
        self.pool = Pool(root)
        self.train = []
        for _ in range(sentences):
            fr, spans = self.pool.sentence(self.rng)
            self.train.append((logmel(fr), frame_targets(len(fr), spans)[0]))
        norm_path = f"{models}/kws_norm.npz"
        if os.path.exists(norm_path) and not fresh_norm:
            z = np.load(norm_path); self.MU, self.SD = z["mu"], z["sd"]
        else:
            allL = np.concatenate([s[0] for s in self.train])
            self.MU, self.SD = allL.mean(0), allL.std(0) + 1e-3
        self.sdt = torch.from_numpy(self.SD.astype(np.float32)).view(1, NM, 1)
        self.idx = [(i, t) for i, s in enumerate(self.train) for t in range(W // 2, len(s[0]) - W // 2) if s[1][t] != IGNORE]
        lab = np.array([self.train[i][1][t] for i, t in self.idx])
        self.byc = [np.where(lab == c)[0] for c in range(len(CLASSES))]
        self.real = load_real(root)
        for r_ in self.real:
            r_["L"] = self.norm(logmel(r_["frames"]))

    def norm(self, L):
        return ((L - self.MU) / self.SD).astype(np.float32)

    def augment(self, X):
        n = len(X)
        X = X + torch.from_numpy(self.rng.uniform(-8, 8, (n, 1, 1)).astype(np.float32)) / self.sdt + 0.15 * torch.randn_like(X)
        for k in range(n):                                              # SpecAugment-style masks
            if self.rng.random() < 0.5:
                a = self.rng.integers(0, NM - 4); X[k, a:a + self.rng.integers(0, 4)] = 0
            if self.rng.random() < 0.5:
                a = self.rng.integers(0, W - 4); X[k, :, a:a + self.rng.integers(0, 4)] = 0
        return X

    def synth_batch(self, n):
        cs = self.rng.choice(len(CLASSES), n, p=self.PROBS)
        X = np.empty((n, NM, W), np.float32)
        for k, c in enumerate(cs):
            i, t = self.idx[self.rng.choice(self.byc[c])]
            X[k] = self.norm(self.train[i][0][t - W // 2:t + W // 2]).T
        return self.augment(torch.from_numpy(X)), torch.from_numpy(cs)

    def pretrain(self, steps=3500, log=print):
        net = KwsCnn()
        opt = torch.optim.AdamW(net.parameters(), 3e-3, weight_decay=1e-3)
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, 6e-3, total_steps=steps)
        t0 = time.time()
        for st in range(steps):
            net.train()
            X, y = self.synth_batch(256)
            loss = Fn.cross_entropy(net(X), y, label_smoothing=0.05)
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
            if st % 700 == 0:
                log(f"  pretrain step {st:4d}  loss {loss.item():.3f}")
        log(f"pretrained in {time.time() - t0:.0f}s")
        return net.eval()

    def real_windows(self, net, utts):
        """Pseudo-labelled windows from real sentences (stride 2): keywords near the aligned centres, background far away."""
        X, y = [], []
        for u in utts:
            L = u["L"]
            starts = list(range(0, len(L) - W + 1, 2))
            cents = np.array(starts) + W // 2
            P = probs(net, L, 2)
            keep = []
            if u["want"]:
                pos = align(np.log(P[:, [CLASSES.index(k) for k in u["want"]]] + 1e-6), D=6)
                keep = [(cents[t], k) for t, k in zip(pos, u["want"])]
            for s, c in zip(starts, cents):
                dist = [abs(c - cc) for cc, _ in keep]
                if keep and min(dist) <= 3:
                    lbl = CLASSES.index(keep[int(np.argmin(dist))][1])
                elif not keep or min(dist) > 14:
                    lbl = 0
                else:
                    continue
                X.append(L[s:s + W].T); y.append(lbl)
        return np.array(X, np.float32), np.array(y)

    def finetune(self, net0, utts, steps=700):
        net = copy.deepcopy(net0)
        Xr, yr = self.real_windows(net0, utts)
        byr = [np.where(yr == c)[0] for c in range(len(CLASSES))]
        opt = torch.optim.AdamW(net.parameters(), 1e-3, weight_decay=1e-3)
        for st in range(steps):
            net.train()
            Xs, ys = self.synth_batch(96)
            cs = self.rng.choice(len(CLASSES), 96, p=self.PROBS)
            xr = torch.from_numpy(np.stack([Xr[self.rng.choice(byr[c])] for c in cs]))
            loss = Fn.cross_entropy(net(torch.cat([Xs, self.augment(xr)])), torch.cat([ys, torch.from_numpy(cs)]), label_smoothing=0.05)
            opt.zero_grad(); loss.backward(); opt.step()
        return net.eval(), len(yr)

    def cv_by_text(self, net0, folds=5, steps=700):
        """Hold out whole prompt texts; returns (results of net0, results of the fine-tuned nets) as [(events, wanted)]."""
        texts = sorted({u["text"] for u in self.real})
        order = self.rng.permutation(len(texts))
        tfold = {texts[i]: k % folds for k, i in enumerate(order)}
        fold = np.array([tfold[u["text"]] for u in self.real])
        res0, res1 = [], []
        for f in range(folds):
            tr = [u for i, u in enumerate(self.real) if fold[i] != f]
            te = [u for i, u in enumerate(self.real) if fold[i] == f]
            net1, _ = self.finetune(net0, tr, steps)
            res0 += [(stream_decode(probs(net0, u["L"])), u["want"]) for u in te]
            res1 += [(stream_decode(probs(net1, u["L"])), u["want"]) for u in te]
        return res0, res1
