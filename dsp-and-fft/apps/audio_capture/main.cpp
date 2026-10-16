// Dataset recorder: on 'g' from the PC, record 1 s from the PDM mic and send it as raw
// little-endian int16 samples, preceded by a 4-byte magic header so the PC can sync.
// PC side: tools/record_dataset.py
// The mic is only running while recording: the PDM driver stops for good if nobody reads it,
// so it is started on 'g', drained in a tight loop, then stopped before the slow USB send.
#include <Arduino.h>
#include <FreeRTOS.h>
#include <task.h>
#include "audio_pdm.h"

#define CLIP_SAMPLES   AUDIO_SAMPLE_RATE        // 1 second
#define SETTLE_SAMPLES 1600                     // discard the first 100 ms (mic start-up)
static const uint8_t pucMagic[4] = {0xA5, 0x5A, 0xA5, 0x5A};

static int16_t sClip[CLIP_SAMPLES];             // 32 KB, static so it is not on a task stack

static bool prvRecordClip() {
  if (!xAudioBegin()) return false;
  static int16_t sScratch[256];
  size_t xSettled = 0, xGot = 0;
  TickType_t xStart = xTaskGetTickCount();
  while (xGot < CLIP_SAMPLES) {
    if (xTaskGetTickCount() - xStart > pdMS_TO_TICKS(3000)) { vAudioEnd(); return false; }
    if (xSettled < SETTLE_SAMPLES) {
      xSettled += xAudioRead(sScratch, 256);
    } else {
      xGot += xAudioRead(&sClip[xGot], CLIP_SAMPLES - xGot);
    }
    vTaskDelay(pdMS_TO_TICKS(1));               // reader must come back within ~16 ms
  }
  vAudioEnd();
  return true;
}

void vCaptureTask(void *pvParameters) {
  for (;;) {
    if (Serial.available() && Serial.read() == 'g') {
      if (prvRecordClip()) {
        Serial.write(pucMagic, sizeof(pucMagic));
        Serial.write((const uint8_t *)sClip, sizeof(sClip));
      }                                         // on failure send nothing; the PC times out
    }
    vTaskDelay(pdMS_TO_TICKS(2));
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  xTaskCreate(vCaptureTask, "capture", 512, NULL, 2, NULL);
}

void loop() { vTaskDelay(pdMS_TO_TICKS(1000)); }
