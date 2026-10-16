#!/usr/bin/env python3
"""Check that the firmware CNN code (common/kws_cnn.cpp + cnn_params.h) matches PyTorch on real recordings.

Runs the C++ on the PC over real utterances from dataset_raw/ and compares, window by window, the class
probabilities, and the keyword events of the streaming decoder.      pixi run python tools/check_cnn.py
"""
import os, subprocess, sys, tempfile

import numpy as np
import torch

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
from kws import *

root = os.path.join(here, "..")
exe = os.path.join(tempfile.gettempdir(), "cnn_host")
subprocess.run(["c++", "-O2", "-std=c++11", "-o", exe, os.path.join(here, "host_test", "cnn_host.cpp"),
                os.path.join(root, "common", "kws_cnn.cpp")], check=True)

z = np.load(os.path.join(root, "models", "kws_norm.npz"))
MU, SD = z["mu"], z["sd"]
net = KwsCnn(); net.load_state_dict(torch.load(os.path.join(root, "models", "kws_cnn.pt"))); net.eval()
STRIDE, HOLD, THETA = 4, 3, 0.5


def py_events(P):
    ev, cand = [], None
    for p in P:
        k = 1 + int(np.argmax(p[1:]))
        if p[k] >= THETA and (cand is None or p[k] > cand[1]):
            cand = [k, p[k], 0]
        elif cand is not None:
            cand[2] += 1
        if cand is not None and cand[2] >= HOLD:
            ev.append(CLASSES[cand[0]]); cand = None
    for _ in range(HOLD):                                   # flush, as the host program does
        if cand is not None:
            ev.append(CLASSES[cand[0]]); cand = None
    return ev


real = load_real(root)
worst, mism, n_win, ev_ok = 0.0, 0, 0, 0
for u in real[::3]:                                          # every third utterance is plenty
    fr = u["frames"]
    x = np.clip(np.round(fr), -32768, 32767).astype("<i2")   # exactly what the board would see
    with tempfile.NamedTemporaryFile(suffix=".raw", delete=False) as f:
        f.write(x.tobytes()); path = f.name
    out = subprocess.run([exe, path], capture_output=True, text=True, check=True).stdout.splitlines(); os.unlink(path)
    cpp_p = np.array([[float(v) for v in l.split()[1:]] for l in out if l.startswith("P")])
    cpp_ev = [l.split()[1] for l in out if l.startswith("EV")]
    L = ((logmel(x.astype(float).reshape(-1, 256)) - MU) / SD).astype(np.float32)
    starts = list(range(0, len(L) - W + 1, STRIDE))
    with torch.no_grad():
        py_p = torch.softmax(net(torch.from_numpy(np.stack([L[s:s + W].T for s in starts]))), 1).numpy()
    assert cpp_p.shape == py_p.shape, (cpp_p.shape, py_p.shape)
    worst = max(worst, float(np.abs(cpp_p - py_p).max())); n_win += len(starts)
    mism += int((cpp_p.argmax(1) != py_p.argmax(1)).sum()); ev_ok += cpp_ev == py_events(py_p)
print(f"{len(real[::3])} utterances, {n_win} windows compared")
print(f"largest probability difference C++ vs PyTorch: {worst:.2e}")
print(f"windows where the predicted class differs:     {mism}")
print(f"utterances with identical decoder events:      {ev_ok}/{len(real[::3])}")
sys.exit(0 if worst < 1e-3 and ev_ok == len(real[::3]) else 1)
