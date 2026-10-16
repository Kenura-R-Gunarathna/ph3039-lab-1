// Approach 3: Edge Impulse keyword spotting.
// TODO: export the project as a C++ library, unzip it into third_party/edge_impulse/, then
// call run_classifier_continuous() here and send LED_CMD_ON / LED_CMD_OFF to xLedQueue.
#include <Arduino.h>
#include <FreeRTOS.h>
#include <task.h>
#include <queue.h>
#include "led_control.h"
#include "audio_pdm.h"

void vVoiceTask(void *pvParameters) {
  for (;;) {
    // 1. fill the inference buffer with xAudioRead()
    // 2. run_classifier_continuous(); if "on" or "off" score > 0.8, queue the command
    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

void setup() {
  Serial.begin(115200);
  vLedInit();
  xAudioBegin();
  xTaskCreate(vLedTask,   "led",   128,  NULL, 2, NULL);
  xTaskCreate(vVoiceTask, "voice", 1024, NULL, 2, NULL);
}

void loop() { vTaskDelay(pdMS_TO_TICKS(1000)); }
