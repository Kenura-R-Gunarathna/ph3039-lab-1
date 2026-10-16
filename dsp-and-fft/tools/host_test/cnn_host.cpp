// Host build of common/kws_cnn.cpp: reads raw int16 frames (256 per frame) from a file, runs the log-mel front end,
// the CNN every KWS_STRIDE frames and the streaming decoder, and prints what the firmware would compute.
#include <cstdio>
#include <vector>
#include "../../common/kws_cnn.h"
#include "../../common/cnn_params.h"

int main(int argc, char **argv) {
  if (argc < 2) return 1;
  FILE *f = fopen(argv[1], "rb");
  if (!f) return 1;
  std::vector<int16_t> x;
  int16_t buf[256];
  while (fread(buf, 2, 256, f) == 256) x.insert(x.end(), buf, buf + 256);
  fclose(f);
  int n = (int)x.size() / 256;
  static float ring[KWS_T][KWS_NM], win[KWS_T][KWS_NM];
  float prob[KWS_NCLASS];
  kwsDecodeReset();
  for (int t = 0; t < n; t++) {
    kwsMelFrame(&x[t * 256], ring[t % KWS_T]);
    int frames = t + 1;
    if (frames >= KWS_T && (frames - KWS_T) % KWS_STRIDE == 0) {
      for (int k = 0; k < KWS_T; k++) for (int m = 0; m < KWS_NM; m++) win[k][m] = ring[(frames + k) % KWS_T][m];
      kwsInfer(&win[0][0], prob);
      printf("P");
      for (int c = 0; c < KWS_NCLASS; c++) printf(" %.7f", prob[c]);
      printf("\n");
      int e = kwsDecode(prob);
      if (e) printf("EV %s\n", kKwsClasses[e]);
    }
  }
  const float bg[KWS_NCLASS] = {1, 0, 0, 0, 0};            // flush a pending keyword at the end of the file
  for (int k = 0; k < KWS_HOLD; k++) { int e = kwsDecode(bg); if (e) printf("EV %s\n", kKwsClasses[e]); }
  return 0;
}
