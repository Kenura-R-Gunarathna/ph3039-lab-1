#include "voice_features.h"
#include <math.h>

#define NBINS (VF_FRAME / 2 + 1)                  // 129 one-sided bins, 62.5 Hz apart

static float sWin[VF_FRAME];                      // scipy default spectrogram window: Tukey(0.25), periodic
static float sCos[VF_FRAME / 2], sSin[VF_FRAME / 2];
static float sScale;                              // scipy 'density' scaling: 1 / (fs * sum(w^2))
static bool  bInit = false;

static float sRe[VF_FRAME], sIm[VF_FRAME];

static void prvInit() {
  const int M = VF_FRAME + 1;                     // periodic window = symmetric window of length N+1, last dropped
  const double alpha = 0.25;
  const int width = (int)floor(alpha * (M - 1) / 2.0);
  double sum2 = 0;
  for (int n = 0; n < VF_FRAME; n++) {
    double w;
    if (n <= width)               w = 0.5 * (1 + cos(M_PI * (-1 + 2.0 * n / alpha / (M - 1))));
    else if (n < M - width - 1)   w = 1.0;
    else                          w = 0.5 * (1 + cos(M_PI * (-2.0 / alpha + 1 + 2.0 * n / alpha / (M - 1))));
    sWin[n] = (float)w;
    sum2 += w * w;
  }
  sScale = (float)(1.0 / (VF_FS * sum2));
  for (int k = 0; k < VF_FRAME / 2; k++) {
    sCos[k] = (float)cos(2 * M_PI * k / VF_FRAME);
    sSin[k] = (float)-sin(2 * M_PI * k / VF_FRAME);
  }
  bInit = true;
}

// In-place radix-2 FFT of sRe/sIm (length VF_FRAME).
static void prvFft() {
  for (int i = 1, j = 0; i < VF_FRAME; i++) {     // bit reversal
    int bit = VF_FRAME >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { float t = sRe[i]; sRe[i] = sRe[j]; sRe[j] = t; t = sIm[i]; sIm[i] = sIm[j]; sIm[j] = t; }
  }
  for (int len = 2; len <= VF_FRAME; len <<= 1) {
    int half = len >> 1, step = VF_FRAME / len;
    for (int i = 0; i < VF_FRAME; i += len) {
      for (int k = 0; k < half; k++) {
        float wr = sCos[k * step], wi = sSin[k * step];
        int a = i + k, b = a + half;
        float tr = sRe[b] * wr - sIm[b] * wi, ti = sRe[b] * wi + sIm[b] * wr;
        sRe[b] = sRe[a] - tr; sIm[b] = sIm[a] - ti;
        sRe[a] += tr;         sIm[a] += ti;
      }
    }
  }
}

// One frame -> scaled one-sided power spectrum S[0..128] (what scipy.signal.spectrogram returns per column).
static void prvSpectrum(const float *pfFrame, float *pfS) {
  float mean = 0;
  for (int i = 0; i < VF_FRAME; i++) mean += pfFrame[i];
  mean /= VF_FRAME;                               // detrend='constant'
  for (int i = 0; i < VF_FRAME; i++) { sRe[i] = (pfFrame[i] - mean) * sWin[i]; sIm[i] = 0; }
  prvFft();
  for (int k = 0; k < NBINS; k++) {
    float p = (sRe[k] * sRe[k] + sIm[k] * sIm[k]) * sScale;
    pfS[k] = (k == 0 || k == NBINS - 1) ? p : 2 * p;   // one-sided: double everything except DC and Nyquist
  }
}

static int prvSign(float v) { return (v > 0) - (v < 0); }

void vfExtract(const int16_t *psClip, int nSamples, float *pfOut) {
  if (!bInit) prvInit();
  int nFrames = nSamples / VF_FRAME;
  if (nFrames > VF_FRAMES) nFrames = VF_FRAMES;
  const int n = nFrames * VF_FRAME;               // samples actually used

  // zcr and crest: per frame, each frame with its own mean removed (immune to slow DC drift)
  static float fZc[VF_FRAMES];                    // per-frame zero-crossing rate
  float sumsq = 0, maxabs = 0;
  int crossings = 0;
  for (int t = 0; t < nFrames; t++) {
    int frameCross = 0;
    const int16_t *pf = psClip + t * VF_FRAME;
    float m = 0;
    for (int i = 0; i < VF_FRAME; i++) m += pf[i];
    m /= VF_FRAME;
    int prevSign = 0;
    for (int i = 0; i < VF_FRAME; i++) {
      float x = pf[i] - m;
      sumsq += x * x;
      if (fabsf(x) > maxabs) maxabs = fabsf(x);
      int sg = prvSign(x);
      if (i > 0 && sg != prevSign) { crossings++; frameCross++; }
      prevSign = sg;
    }
    fZc[t] = (float)frameCross / (VF_FRAME - 1);
  }
  float rms = sqrtf(sumsq / n);

  // pass 1: per-frame energy (dB) and energy above 3 kHz
  static float fDb[VF_FRAMES], fHi[VF_FRAMES], fS[NBINS], fFrame[VF_FRAME];
  float dbMax = -1e30f;
  for (int t = 0; t < nFrames; t++) {
    for (int i = 0; i < VF_FRAME; i++) fFrame[i] = psClip[t * VF_FRAME + i];
    prvSpectrum(fFrame, fS);
    float e = 0, hi = 0;
    for (int k = 0; k < NBINS; k++) { e += fS[k]; if (k * 62.5f >= 3000.0f) hi += fS[k]; }
    fDb[t] = 10.0f * log10f(e + 1e-9f);
    fHi[t] = hi;
    if (fDb[t] > dbMax) dbMax = fDb[t];
  }

  // floor = 20th percentile of the frame energies (numpy linear interpolation)
  static float fSorted[VF_FRAMES];
  for (int t = 0; t < nFrames; t++) fSorted[t] = fDb[t];
  for (int i = 1; i < nFrames; i++) { float v = fSorted[i]; int j = i - 1; while (j >= 0 && fSorted[j] > v) { fSorted[j + 1] = fSorted[j]; j--; } fSorted[j + 1] = v; }
  float pos = 0.2f * (nFrames - 1);
  int lo = (int)pos;
  float floorDb = fSorted[lo] + (pos - lo) * (fSorted[lo + 1 < nFrames ? lo + 1 : lo] - fSorted[lo]);

  // active frames: more than 10 dB above the floor
  static bool bAct[VF_FRAMES];
  int nAct = 0, first = -1, last = -1, argMaxDb = 0;
  for (int t = 0; t < nFrames; t++) {
    bAct[t] = fDb[t] > floorDb + 10.0f;
    if (fDb[t] > fDb[argMaxDb]) argMaxDb = t;
  }
  bool any = false;
  for (int t = 0; t < nFrames; t++) any |= bAct[t];
  if (!any) bAct[argMaxDb] = true;
  for (int t = 0; t < nFrames; t++) if (bAct[t]) { nAct++; if (first < 0) first = t; last = t; }

  // the active frames, in order, are split into 3 consecutive parts like numpy.array_split
  // (sizes q+1 for the first r parts, q for the rest); with fewer than 3 active frames every part is all of them
  int q = nAct / 3, r = nAct % 3, rank = 0;
  static int8_t iPartMask[VF_FRAMES];             // bit p set = this frame belongs to part p
  for (int t = 0; t < nFrames; t++) {
    iPartMask[t] = 0;
    if (!bAct[t]) continue;
    if (nAct < 3) iPartMask[t] = 7;
    else iPartMask[t] = 1 << (rank < r * (q + 1) ? rank / (q + 1) : r + (rank - r * (q + 1)) / q);
    rank++;
  }

  // pass 2: energy per bin summed over the active frames, overall and per part
  static float fSa[NBINS], fSp[3][NBINS];
  for (int k = 0; k < NBINS; k++) { fSa[k] = 0; fSp[0][k] = fSp[1][k] = fSp[2][k] = 0; }
  for (int t = 0; t < nFrames; t++) {
    if (!bAct[t]) continue;
    for (int i = 0; i < VF_FRAME; i++) fFrame[i] = psClip[t * VF_FRAME + i];
    prvSpectrum(fFrame, fS);
    for (int k = 0; k < NBINS; k++) {
      fSa[k] += fS[k];
      for (int p = 0; p < 3; p++) if (iPartMask[t] & (1 << p)) fSp[p][k] += fS[k];
    }
  }
  float tot = 1e-9f, centNum = 0;
  for (int k = 0; k < NBINS; k++) { tot += fSa[k]; centNum += k * 62.5f * fSa[k]; }
  static const int kBand[4][2] = {{100, 500}, {500, 1500}, {1500, 3000}, {3000, 8000}};
  float band[4];
  for (int b = 0; b < 4; b++) {
    float s = 0;
    for (int k = 0; k < NBINS; k++) { float f = k * 62.5f; if (f >= kBand[b][0] && f < kBand[b][1]) s += fSa[k]; }
    band[b] = s / tot;
  }

  // hipos: where the >3 kHz energy peaks inside the active span (first maximum, like numpy.argmax)
  int argHi = 0;
  float bestHi = bAct[0] ? fHi[0] : 0;
  for (int t = 1; t < nFrames; t++) { float v = bAct[t] ? fHi[t] : 0; if (v > bestHi) { bestHi = v; argHi = t; } }
  int spanFrames = last - first; if (spanFrames < 1) spanFrames = 1;

  pfOut[0]  = nAct * 0.016f;                           // dur
  pfOut[1]  = (last - first + 1) * 0.016f;             // span
  pfOut[2]  = dbMax - floorDb;                         // peak_db
  pfOut[3]  = band[0]; pfOut[4] = band[1]; pfOut[5] = band[2]; pfOut[6] = band[3];
  pfOut[7]  = centNum / tot;                           // cent
  pfOut[8]  = (float)(argHi - first) / spanFrames;     // hipos
  pfOut[9]  = (float)crossings / (nFrames * (VF_FRAME - 1));   // zcr
  pfOut[10] = maxabs / (rms + 1e-9f);                  // crest

  // temporal features: band shares, zero-crossing rate and relative level of each third of the word
  for (int p = 0; p < 3; p++) {
    float pTot = 1e-9f;
    for (int k = 0; k < NBINS; k++) pTot += fSp[p][k];
    for (int b = 0; b < 4; b++) {
      float sb = 0;
      for (int k = 0; k < NBINS; k++) { float f = k * 62.5f; if (f >= kBand[b][0] && f < kBand[b][1]) sb += fSp[p][k]; }
      pfOut[11 + p * 5 + b] = sb / pTot;
    }
    float zSum = 0, dSum = 0; int cnt = 0;
    for (int t = 0; t < nFrames; t++) if (iPartMask[t] & (1 << p)) { zSum += fZc[t]; dSum += fDb[t]; cnt++; }
    pfOut[11 + p * 5 + 4] = zSum / cnt;
    pfOut[26 + p] = dSum / cnt - dbMax;
  }
}
