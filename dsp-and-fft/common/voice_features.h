#pragma once
#include <stdint.h>

// C++ port of tools/voice_features.py::extract(): same 29 features, same order.
// Plain C++ (no Arduino) so tools/check_features.py can compile it on the PC and compare.
#define VF_FS            16000
#define VF_FRAME         256                      // 16 ms
#define VF_FRAMES        42                       // frames per classified window (= WINDOW_FRAMES in voice_features.py)
#define VF_CLIP_SAMPLES  (VF_FRAME * VF_FRAMES)   // 10752 samples
#define VF_TRAIN_SKIP_FRAMES 20                   // recorded dataset clips skip this many start-up frames (SKIP_FRAMES in .py)
#define VF_NUM_FEATURES  29

// Order: dur span peak_db b0 b1 b2 b3 cent hipos zcr crest, then for the start / middle / end third of the
//        active frames: p1_b0 p1_b1 p1_b2 p1_b3 p1_zcr p2_... p3_..., then p1_lvl p2_lvl p3_lvl
// psClip: nSamples int16 samples (at least one frame, at most VF_CLIP_SAMPLES). Not re-entrant.
void vfExtract(const int16_t *psClip, int nSamples, float *pfOut);
