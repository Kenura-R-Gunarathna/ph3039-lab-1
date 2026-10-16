// Host build of common/voice_features.cpp: reads WAV paths from argv, prints the 11 features per clip.
#include <cstdio>
#include <cstring>
#include <vector>
#include "../../common/voice_features.h"

static bool readWav(const char *path, std::vector<int16_t> &out) {
  FILE *f = fopen(path, "rb");
  if (!f) return false;
  char id[4]; unsigned int size;
  fseek(f, 12, SEEK_SET);                                   // after RIFF header + "WAVE"
  while (fread(id, 1, 4, f) == 4 && fread(&size, 4, 1, f) == 1) {
    if (!memcmp(id, "data", 4)) { out.resize(size / 2); fread(out.data(), 2, out.size(), f); fclose(f); return true; }
    fseek(f, size, SEEK_CUR);
  }
  fclose(f);
  return false;
}

int main(int argc, char **argv) {
  for (int i = 1; i < argc; i++) {
    std::vector<int16_t> x;
    if (!readWav(argv[i], x) || (int)x.size() < (VF_TRAIN_SKIP_FRAMES + VF_FRAMES) * VF_FRAME) { fprintf(stderr, "bad wav %s\n", argv[i]); return 1; }
    float f[VF_NUM_FEATURES];
    vfExtract(x.data() + VF_TRAIN_SKIP_FRAMES * VF_FRAME, VF_CLIP_SAMPLES, f);   // same window the Python training uses
    for (int k = 0; k < VF_NUM_FEATURES; k++) printf("%.9g%c", f[k], k + 1 < VF_NUM_FEATURES ? ' ' : '\n');
  }
  return 0;
}
