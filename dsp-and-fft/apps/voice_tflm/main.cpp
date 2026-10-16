// Approach 2: TensorFlow Lite Micro with your own model.
// TODO: train in training/tflm/, export model_data.h, put the TFLM sources in third_party/,
// then: MFCC (CMSIS-DSP) -> interpreter.Invoke() -> send LED_CMD_ON / LED_CMD_OFF to xLedQueue.
#include <Arduino.h>
#include <FreeRTOS.h>
#include <task.h>
#include <queue.h>
#include "led_control.h"
#include "audio_pdm.h"

void vVoiceTask(void *pvParameters) {
  for (;;) {
    // 1. read ~1 s of audio with xAudioRead()
    // 2. compute MFCC features
    // 3. run the model, pick the best class
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
