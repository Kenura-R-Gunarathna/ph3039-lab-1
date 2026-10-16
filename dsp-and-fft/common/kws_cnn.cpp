#include "kws_cnn.h"
#include "cnn_params.h"
#include <math.h>
#include <string.h>

#define NBINS 129                                   // one-sided FFT bins of a 256-sample frame

// ------------------------------------------------------------------ log-mel front end
static float sHann[256], sCos[128], sSin[128];
static float sMel[KWS_NM][NBINS];                    // triangular mel filters (dense, 16 KB)
static bool  bMelInit = false;
static float sRe[256], sIm[256];

static void prvMelInit() {
  for (int n = 0; n < 256; n++) sHann[n] = (float)(0.5 - 0.5 * cos(2 * M_PI * n / 255.0));    // numpy.hanning(256)
  for (int k = 0; k < 128; k++) { sCos[k] = (float)cos(2 * M_PI * k / 256.0); sSin[k] = (float)-sin(2 * M_PI * k / 256.0); }
  const double lo = 100, hi = 7600;
  auto hz2m = [](double f) { return 2595 * log10(1 + f / 700); };
  auto m2hz = [](double m) { return 700 * (pow(10, m / 2595) - 1); };
  double pts[KWS_NM + 2];
  for (int i = 0; i < KWS_NM + 2; i++) pts[i] = m2hz(hz2m(lo) + (hz2m(hi) - hz2m(lo)) * i / (KWS_NM + 1));
  for (int i = 0; i < KWS_NM; i++) {
    double a = pts[i], b = pts[i + 1], c = pts[i + 2];
    for (int k = 0; k < NBINS; k++) {
      double f = k * 62.5, v = fmin((f - a) / (b - a), (c - f) / (c - b));
      sMel[i][k] = (float)(v > 0 ? v : 0);
    }
  }
  bMelInit = true;
}

static void prvFft() {                               // in-place radix-2 FFT of sRe / sIm
  for (int i = 1, j = 0; i < 256; i++) {
    int bit = 128;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) { float t = sRe[i]; sRe[i] = sRe[j]; sRe[j] = t; t = sIm[i]; sIm[i] = sIm[j]; sIm[j] = t; }
  }
  for (int len = 2; len <= 256; len <<= 1) {
    int half = len >> 1, step = 256 / len;
    for (int i = 0; i < 256; i += len)
      for (int k = 0; k < half; k++) {
        float wr = sCos[k * step], wi = sSin[k * step];
        int a = i + k, b = a + half;
        float tr = sRe[b] * wr - sIm[b] * wi, ti = sRe[b] * wi + sIm[b] * wr;
        sRe[b] = sRe[a] - tr; sIm[b] = sIm[a] - ti;
        sRe[a] += tr;         sIm[a] += ti;
      }
  }
}

void kwsMelFrame(const int16_t *psFrame, float *pfOut) {
  if (!bMelInit) prvMelInit();
  float mean = 0;
  for (int i = 0; i < 256; i++) mean += psFrame[i];
  mean /= 256;
  for (int i = 0; i < 256; i++) { sRe[i] = (psFrame[i] - mean) * sHann[i]; sIm[i] = 0; }
  prvFft();
  static float fPow[NBINS];
  for (int k = 0; k < NBINS; k++) fPow[k] = sRe[k] * sRe[k] + sIm[k] * sIm[k];
  for (int m = 0; m < KWS_NM; m++) {
    float e = 0;
    for (int k = 0; k < NBINS; k++) e += fPow[k] * sMel[m][k];
    pfOut[m] = ((10.0f * log10f(e + 1.0f)) - kKwsMean[m]) / kKwsStd[m];
  }
}

// ------------------------------------------------------------------ 1D CNN (float, BatchNorm already folded in)
// out[t][o] = relu(bias[o] + sum_k sum_i w[o][k][i] * in[t*stride + k - 1][i])   (kernel 3, zero padding 1)
static void prvConv(const float *pfIn, int nIn, int cIn, float *pfOut, int *pnOut, int cOut, int stride, const float *pfW, const float *pfB) {
  int nOut = (nIn + 2 - 3) / stride + 1;
  for (int t = 0; t < nOut; t++)
    for (int o = 0; o < cOut; o++) {
      float acc = pfB[o];
      const float *w = pfW + o * 3 * cIn;
      for (int k = 0; k < 3; k++) {
        int ti = t * stride + k - 1;
        if (ti < 0 || ti >= nIn) continue;
        const float *x = pfIn + ti * cIn;
        const float *wk = w + k * cIn;
        for (int i = 0; i < cIn; i++) acc += wk[i] * x[i];
      }
      pfOut[t * cOut + o] = acc > 0 ? acc : 0;
    }
  *pnOut = nOut;
}

void kwsInfer(const float *pfWin, float *pfProb) {
  static float bufA[KWS_T * 32], bufB[KWS_T * 32];     // max activations: 42 x 32 floats
  int n1, n2, n3, n4;
  prvConv(pfWin, KWS_T, KWS_NM, bufA, &n1, 32, 1, &kConv1W[0][0][0], kConv1B);
  prvConv(bufA, n1, 32, bufB, &n2, 48, 2, &kConv2W[0][0][0], kConv2B);
  prvConv(bufB, n2, 48, bufA, &n3, 64, 2, &kConv3W[0][0][0], kConv3B);
  prvConv(bufA, n3, 64, bufB, &n4, 64, 1, &kConv4W[0][0][0], kConv4B);
  float feat[128];
  for (int c = 0; c < 64; c++) {                       // [mean over time, max over time]
    float s = 0, m = bufB[c];
    for (int t = 0; t < n4; t++) { float v = bufB[t * 64 + c]; s += v; if (v > m) m = v; }
    feat[c] = s / n4; feat[64 + c] = m;
  }
  float logit[KWS_NCLASS], mx = -1e30f;
  for (int c = 0; c < KWS_NCLASS; c++) {
    float acc = kFcB[c];
    for (int i = 0; i < 128; i++) acc += kFcW[c][i] * feat[i];
    logit[c] = acc; if (acc > mx) mx = acc;
  }
  float sum = 0;
  for (int c = 0; c < KWS_NCLASS; c++) { pfProb[c] = expf(logit[c] - mx); sum += pfProb[c]; }
  for (int c = 0; c < KWS_NCLASS; c++) pfProb[c] /= sum;
}

// ------------------------------------------------------------------ streaming decoder
static int   iCand = 0, iAge = 0;                     // pending keyword class (0 = none) and windows since its peak
static float fCandP = 0;

void kwsDecodeReset() { iCand = 0; iAge = 0; fCandP = 0; }

int kwsDecode(const float *pfProb) {
  int k = 1;
  for (int c = 2; c < KWS_NCLASS; c++) if (pfProb[c] > pfProb[k]) k = c;
  if (pfProb[k] >= KWS_THETA && (iCand == 0 || pfProb[k] > fCandP)) { iCand = k; fCandP = pfProb[k]; iAge = 0; }
  else if (iCand != 0) iAge++;
  if (iCand != 0 && iAge >= KWS_HOLD) { int e = iCand; kwsDecodeReset(); return e; }
  return 0;
}
