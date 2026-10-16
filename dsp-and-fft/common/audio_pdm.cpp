#include "audio_pdm.h"
#include <PDM.h>

bool xAudioBegin() {
  PDM.setBufferSize(512);
  PDM.setGain(20);
  return PDM.begin(1, AUDIO_SAMPLE_RATE) == 1;
}

size_t xAudioRead(int16_t *psBuffer, size_t xSamples) {
  int iBytes = PDM.available();
  if (iBytes <= 0) return 0;
  size_t xWant = xSamples * sizeof(int16_t);
  if ((size_t)iBytes > xWant) iBytes = (int)xWant;
  return PDM.read(psBuffer, iBytes) / sizeof(int16_t);
}

void vAudioEnd() {
  PDM.end();
}
