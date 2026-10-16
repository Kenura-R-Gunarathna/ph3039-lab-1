// Approach 2: 1D CNN keyword spotter (log-mel + CNN, trained with tools/train_cnn.py).
//
//   mic -> 16 ms frames -> 32 log-mel values per frame -> every 4 frames the CNN looks at the last 42 frames
//       -> class probabilities (bg, blue, green, off, on) -> streaming decoder -> keyword events
//       -> command logic (order independent) -> LED
//
// No word cutting: the CNN runs on overlapping windows, so words said back to back are fine.
// Command logic: a colour word (green / blue) selects the LED, "on" / "off" is the action. They can come in either
// order within a few seconds, and other words in between are ignored:
//   "blue on", "blue led on", "switch on blue", "on blue" ...
// A lone "on" / "off" with no colour within 1.2 s acts on the last LED that was used (green at start).
//
// Serial output: "EV <word> <prob>" for every keyword heard, "CMD <LED> <on|off>" for every command.
// Retrain:  pixi run train-cnn   (writes common/cnn_params.h), then make APP=voice_cnn flash.
#include <Arduino.h>
#include <FreeRTOS.h>
#include <task.h>
#include <semphr.h>
#include <math.h>
#include <string.h>
#include "led_control.h"
#include "audio_pdm.h"
#include "kws_cnn.h"
#include "cnn_params.h"

#define SETTLE_FRAMES   60         // ~1 s after the mic (re)starts: its output is unreliable, ignore keywords
#define TARGET_MS       2500       // a colour word stays valid this long
#define ACTION_MS       2500       // an action word stays valid this long
#define LONE_ACTION_MS  1200       // an action with no colour for this long acts on the last-used LED
#define VOICE_DEBUG     1          // status line every 2 s (set 0 to silence)

static float sMelRing[KWS_T][KWS_NM];                  // the last 42 normalised log-mel frames (circular)
static volatile uint32_t ulFrames = 0;                 // frames written so far
static volatile int iSettle = SETTLE_FRAMES;
static SemaphoreHandle_t xWindowReady;

static volatile bool bMicOk = false;
static volatile uint32_t ulDbgRestarts = 0, ulInferUs = 0;
static volatile float fDbgRms = 0, fDbgLoudest = 0;

static float prvFrameRms(const int16_t *psFrame) {
  float fMean = 0;
  for (int i = 0; i < 256; i++) fMean += psFrame[i];
  fMean /= 256;
  float fSum = 0;
  for (int i = 0; i < 256; i++) { float d = psFrame[i] - fMean; fSum += d * d; }
  return sqrtf(fSum / 256);
}

// Task 1 (high priority): keeps the mic drained and turns every frame into 32 log-mel values
void vAudioTask(void *pvParameters) {
  static int16_t sFrame[256];
  size_t xFilled = 0;

  // Start the mic HERE: the PDM driver switches itself off for good if nobody reads within ~16 ms of starting.
  bMicOk = xAudioBegin();
  TickType_t xLastAudio = xTaskGetTickCount();

  for (;;) {
    size_t xGot = xAudioRead(sFrame + xFilled, 256 - xFilled);
    xFilled += xGot;
    if (xGot > 0) xLastAudio = xTaskGetTickCount();
    if (xFilled < 256) {
      // Watchdog: the first start after boot delivers one empty buffer and then stalls; the driver also stops
      // for good if it ever overflows. No audio for 250 ms -> restart the mic.
      if (xTaskGetTickCount() - xLastAudio > pdMS_TO_TICKS(250)) {
        vAudioEnd();
        vTaskDelay(pdMS_TO_TICKS(150));
        bMicOk = xAudioBegin();
        xFilled = 0; xLastAudio = xTaskGetTickCount(); ulDbgRestarts++;
        iSettle = SETTLE_FRAMES;
      }
      vTaskDelay(pdMS_TO_TICKS(1));
      continue;
    }
    xFilled = 0;

    float fRms = prvFrameRms(sFrame);
    fDbgRms = fRms;
    if (fRms > fDbgLoudest) fDbgLoudest = fRms;

    uint32_t ulRow = ulFrames % KWS_T;
    taskENTER_CRITICAL();                              // keep the CNN task from reading a half-written row
    kwsMelFrame(sFrame, sMelRing[ulRow]);
    ulFrames++;
    taskEXIT_CRITICAL();
    if (iSettle > 0) iSettle--;
    if (ulFrames >= KWS_T && ulFrames % KWS_STRIDE == 0) xSemaphoreGive(xWindowReady);
  }
}

// ---- command logic: colour + action in either order ----
static int iTarget = -1, iAction = -1, iLastLed = 0;   // LED: 0 = green, 1 = blue;  action: 0 = off, 1 = on
static uint32_t ulTargetMs = 0, ulActionMs = 0;

static void prvExecute(int iLed, int iOn) {
  LedCommand_t xCmd = iLed ? (iOn ? LED_CMD_BLUE_ON : LED_CMD_BLUE_OFF) : (iOn ? LED_CMD_GREEN_ON : LED_CMD_GREEN_OFF);
  xQueueSend(xLedQueue, &xCmd, 0);
  iLastLed = iLed; iTarget = -1; iAction = -1;
  Serial.print("CMD "); Serial.print(iLed ? "BLUE " : "GREEN "); Serial.println(iOn ? "on" : "off");
}

static void prvCommandTick(uint32_t ulNow) {
  if (iTarget >= 0 && ulNow - ulTargetMs > TARGET_MS) iTarget = -1;
  if (iAction >= 0) {
    if (iTarget >= 0)                                  prvExecute(iTarget, iAction);
    else if (ulNow - ulActionMs >= LONE_ACTION_MS)     prvExecute(iLastLed, iAction);
    else if (ulNow - ulActionMs > ACTION_MS)           iAction = -1;
  }
}

static void prvKeyword(const char *pcName, float fProb, uint32_t ulNow) {
  Serial.print("EV "); Serial.print(pcName); Serial.print(" "); Serial.println(fProb, 2);
  if (!strcmp(pcName, "green"))     { iTarget = 0; ulTargetMs = ulNow; iLastLed = 0; }
  else if (!strcmp(pcName, "blue")) { iTarget = 1; ulTargetMs = ulNow; iLastLed = 1; }
  else if (!strcmp(pcName, "on"))   { iAction = 1; ulActionMs = ulNow; }
  else if (!strcmp(pcName, "off"))  { iAction = 0; ulActionMs = ulNow; }
  prvCommandTick(ulNow);
}

// Task 2 (lower priority): CNN on the latest window every 4 frames, then decoder and command logic
void vCnnTask(void *pvParameters) {
  static float sWin[KWS_T][KWS_NM];
  float fProb[KWS_NCLASS];
  for (;;) {
    xSemaphoreTake(xWindowReady, portMAX_DELAY);
    taskENTER_CRITICAL();
    uint32_t ulNow = ulFrames;                         // oldest row of the circular buffer is at ulNow % 42
    for (int t = 0; t < KWS_T; t++) memcpy(sWin[t], sMelRing[(ulNow + t) % KWS_T], sizeof(sWin[t]));
    taskEXIT_CRITICAL();
    if (iSettle > 0) { kwsDecodeReset(); continue; }

    uint32_t ulT0 = micros();
    kwsInfer(&sWin[0][0], fProb);
    ulInferUs = micros() - ulT0;
    int iEvent = kwsDecode(fProb);
    uint32_t ulMs = millis();
    if (iEvent) prvKeyword(kKwsClasses[iEvent], fProb[iEvent], ulMs);
    else        prvCommandTick(ulMs);
  }
}

void setup() {
  Serial.begin(115200);
  uint32_t ulStart = millis();
  while (!Serial && millis() - ulStart < 2000) delay(10);   // works with or without a USB serial monitor

  vLedInit();
  xWindowReady = xSemaphoreCreateBinary();
  Serial.print("voice_cnn ready, classes:");
  for (int c = 0; c < KWS_NCLASS; c++) { Serial.print(" "); Serial.print(kKwsClasses[c]); }
  Serial.println("  (stay quiet for 1 s)");

  xTaskCreate(vLedTask,   "led",   128, NULL, 2, NULL);
  xTaskCreate(vAudioTask, "audio", 384, NULL, 3, NULL);
  xTaskCreate(vCnnTask,   "cnn",   512, NULL, 2, NULL);
}

void loop() {
  vTaskDelay(pdMS_TO_TICKS(2000));
#if VOICE_DEBUG
  Serial.print(bMicOk ? "  . frame rms " : "  . MIC FAILED frame rms "); Serial.print(fDbgRms, 0);
  Serial.print("  loudest (2 s) "); Serial.print(fDbgLoudest, 0);
  Serial.print("  cnn "); Serial.print(ulInferUs / 1000.0f, 1); Serial.print(" ms");
  Serial.print("  frames "); Serial.print(ulFrames); Serial.print(" restarts "); Serial.println(ulDbgRestarts);
  fDbgLoudest = 0;
#endif
}
