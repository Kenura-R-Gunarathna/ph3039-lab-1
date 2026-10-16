#!/usr/bin/env python3
"""Check that the firmware feature code (common/voice_features.cpp) matches tools/voice_features.py.

Compiles the C++ for the PC, runs it on clips from dataset/, and compares with the Python features.
    pixi run python tools/check_features.py [--per-class 15]
"""
import argparse, glob, os, subprocess, sys

import numpy as np

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
import voice_features as vf

ap = argparse.ArgumentParser()
ap.add_argument("--per-class", type=int, default=15)
ap.add_argument("--data", default=os.path.join(here, "..", "dataset"))
args = ap.parse_args()

exe = "/tmp/features_host"
subprocess.run(["c++", "-O2", "-std=c++11", "-o", exe, os.path.join(here, "host_test", "features_host.cpp"),
                os.path.join(here, "..", "common", "voice_features.cpp")], check=True)

paths = []
for d in sorted(glob.glob(os.path.join(args.data, "*/"))):
    if os.path.basename(d.rstrip("/")).startswith("_"):
        continue
    paths += sorted(glob.glob(d + "*.wav"))[:args.per_class]
out = subprocess.run([exe, *paths], capture_output=True, text=True, check=True).stdout.split("\n")
C = np.array([[float(v) for v in line.split()] for line in out if line.strip()])
P = np.array([vf.extract(vf.read_wav(p)[vf.SKIP_FRAMES * 256:(vf.SKIP_FRAMES + vf.WINDOW_FRAMES) * 256]) for p in paths])

print(f"{len(paths)} clips compared\n")
print(f"{'feature':8s} {'max |err|':>10s} {'max rel err':>12s} {'clips off by >1%':>17s}")
bad_any = False
for i, n in enumerate(vf.FEATURE_NAMES):
    err = np.abs(C[:, i] - P[:, i]); rel = err / (np.abs(P[:, i]) + 1e-6)
    bad = int((rel > 0.01).sum()); bad_any |= bad > 0
    print(f"{n:8s} {err.max():10.4g} {rel.max():12.3g} {bad:17d}")
sys.exit(1 if bad_any else 0)
