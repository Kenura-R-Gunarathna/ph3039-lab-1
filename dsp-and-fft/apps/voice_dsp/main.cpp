// Approach 1: hand-written DSP + a small trained model (no ML framework).
//
//   mic -> 16 ms frames -> onset detector -> capture until the word ends (or 42 frames)
//       -> 11 DSP features (common/voice_features.cpp) -> z-score + logistic regression (model_params.h)
//       -> class -> LED command
//
// Retrain / change words:  pixi run train-export ...   (writes model_params.h), then rebuild.
// Words are matched by class name: "on" / "off" act on the selected LED; "green" / "blue" select it
// (green is selected at start). Any other class (e.g. "noise") is ignored.
//
// Words said back to back: capture stops ~64 ms after the sound dies down, so each word gets its own
// clip; the unused rest of the 42-frame window is filled with background noise (the quiet frames from
// before the word). Two clip buffers let the next word be captured while the last one is classified.
// Words run together with no dip in loudness cannot be separated this way.
#include <Arduino.h>
#include <FreeRTOS.h>
#include <task.h>
#include <queue.h>
#include <math.h>
#include <string.h>
#include "led_control.h"
#include "audio_pdm.h"
#include "voice_features.h"
#include "model_params.h"

#define PREROLL_FRAMES    10       // 0.16 s kept from before the onset
#define PAD_SRC_FRAMES    7        // quiet pre-roll frames reused as background padding (the last few hold the onset)
#define TRIG_MIN_RMS      300.0f   // a frame must be at least this loud (DC removed) ...
#define TRIG_FACTOR       4.0f     // ... and this many times the tracked background level
#define TRIG_FRAMES       2        // for this many frames in a row
#define END_RMS           120.0f   // word is over when frames stay below this ...
#define END_QUIET_FRAMES  4        // ... for this many frames (64 ms)
#define MIN_WORD_FRAMES   5        // never end a capture sooner than this after the pre-roll
#define TAIL_FRAMES       3        // quiet frames kept after the word
#define WARMUP_FRAMES     40       // ~0.6 s to learn the background level at start
#define REFRACTORY_FRAMES 3        // 48 ms deaf time after a capture
#define MIN_CONFIDENCE    0.60f    // ignore a prediction less sure than this
#define VOICE_DEBUG       1        // print the background / loudest level every 2 s (set 0 to silence)
#define STALE_PREROLL_FIX 1        // replace lead-in frames that still belong to the previous word with background

// Serial commands from the PC (tools/live_session.py): 'S' = send every captured window as binary instead of
// text, 'T' = back to text, 'G' = capture the next 42 frames now (test without speaking).
// Binary frame: A5 5A A5 5A | kept frames | predicted class | probability*255 | 0 | 42*256 int16 samples
// 'R' = raw mode (tools/raw_session.py): every 16 ms frame is streamed as A5 5A A5 5A | seq lo | seq hi | 256 int16,
// detection and classification are switched off; 'T' ends it.

static int16_t sClip[2][VF_CLIP_SAMPLES];      // two windows: one being captured, one being classified
static int16_t sPre[PREROLL_FRAMES][VF_FRAME]; // rolling pre-roll, updated every frame
static volatile bool bBusy[2] = {false, false};
static QueueHandle_t xClipQueue;               // items: (frames kept << 8) | buffer index

static int16_t sBg[PAD_SRC_FRAMES][VF_FRAME];  // quiet frames used to replace a stale lead-in
static volatile bool bStream = false, bForce = false, bRaw = false;
#define RAW_RING 48                            // frames buffered between the audio task and the USB writer (0.77 s)
static int16_t sRaw[RAW_RING][VF_FRAME];
static uint16_t usRawSeqOf[RAW_RING];          // sequence number of the frame in each slot (gaps = dropped frames)
static volatile uint16_t usRawHead = 0, usRawTail = 0, usRawSeq = 0;
static volatile uint32_t ulRawDrops = 0;
static volatile bool bMicOk = false;
static volatile uint32_t ulDbgFrames = 0, ulDbgRestarts = 0;
static volatile float fDbgMean = 0, fDbgFloor = 0, fDbgThreshold = 0, fDbgLoudest = 0;
static volatile int16_t sDbgSample[4];

// RMS of one frame with its DC offset removed
static float prvFrameRms(const int16_t *psFrame) {
  float fMean = 0;
  for (int i = 0; i < VF_FRAME; i++) fMean += psFrame[i];
  fMean /= VF_FRAME;
  float fSum = 0;
  for (int i = 0; i < VF_FRAME; i++) { float d = psFrame[i] - fMean; fSum += d * d; }
  return sqrtf(fSum / VF_FRAME);
}

// Task 1 (high priority): never lets the mic buffer overflow; detects a word, captures it until it ends
void vAudioTask(void *pvParameters) {
  static int16_t sFrame[VF_FRAME];
  size_t xFilled = 0;
  int iPreHead = 0, iPreCount = 0, iWarm = 0, iHot = 0, iCaptured = 0, iQuiet = 0, iRefractory = 0, iBuf = 0, iSinceEnd = 99;
  bool bCapturing = false, bHaveBg = false;
  float fFloor = 0;

  // Start the mic HERE, right before the first read: the PDM driver switches itself off for good
  // if nobody reads within ~16 ms of starting (so it must not be started in setup()).
  bMicOk = xAudioBegin();
  TickType_t xLastAudio = xTaskGetTickCount();

  for (;;) {
    size_t xGot = xAudioRead(sFrame + xFilled, VF_FRAME - xFilled);
    xFilled += xGot;
    if (xGot > 0) xLastAudio = xTaskGetTickCount();
    if (xFilled < VF_FRAME) {
      // Watchdog: the first start after boot delivers one empty buffer and then stalls, and the driver
      // also stops for good if it ever overflows. No audio for 250 ms -> restart the mic.
      if (xTaskGetTickCount() - xLastAudio > pdMS_TO_TICKS(250)) {
        vAudioEnd();
        vTaskDelay(pdMS_TO_TICKS(150));      // let the mic power down fully before starting it again
        bMicOk = xAudioBegin();
        xFilled = 0; xLastAudio = xTaskGetTickCount(); ulDbgRestarts++;
        iPreCount = 0; bCapturing = false; iHot = 0;      // the audio is no longer contiguous
      }
      vTaskDelay(pdMS_TO_TICKS(1));
      continue;
    }
    xFilled = 0;
    float fRms = prvFrameRms(sFrame);
    if (iSinceEnd < 99) iSinceEnd++;
    ulDbgFrames++; for (int i = 0; i < 4; i++) sDbgSample[i] = sFrame[100 + i];
    { float fM = 0; for (int i = 0; i < VF_FRAME; i++) fM += sFrame[i]; fDbgMean = fM / VF_FRAME; }
    if (fRms > fDbgLoudest) fDbgLoudest = fRms;

    // the pre-roll always holds the last PREROLL_FRAMES frames, also while capturing
    memcpy(sPre[iPreHead], sFrame, sizeof(sFrame));
    iPreHead = (iPreHead + 1) % PREROLL_FRAMES;
    if (iPreCount < PREROLL_FRAMES) iPreCount++;

    if (bRaw) {                                        // raw streaming: hand the frame to vRawTask, no detection
      uint16_t usNext = (usRawHead + 1) % RAW_RING;
      if (usNext != usRawTail) { memcpy(sRaw[usRawHead], sFrame, sizeof(sFrame)); usRawSeqOf[usRawHead] = usRawSeq; usRawHead = usNext; }
      else ulRawDrops++;
      usRawSeq++;
      bCapturing = false; iHot = 0;
      continue;
    }

    if (bCapturing) {
      memcpy(&sClip[iBuf][iCaptured * VF_FRAME], sFrame, sizeof(sFrame));
      iCaptured++;
      iQuiet = (fRms < END_RMS) ? iQuiet + 1 : 0;
      bool bEnded = (iQuiet >= END_QUIET_FRAMES && iCaptured >= PREROLL_FRAMES + MIN_WORD_FRAMES);
      if (bEnded || iCaptured == VF_FRAMES) {
        int iKeep = bEnded ? iCaptured - iQuiet + TAIL_FRAMES : iCaptured;
        if (iKeep > iCaptured) iKeep = iCaptured;
        for (int f = iKeep; f < VF_FRAMES; f++)           // pad with background noise from the quiet pre-roll
          memcpy(&sClip[iBuf][f * VF_FRAME], &sClip[iBuf][((f - iKeep) % PAD_SRC_FRAMES) * VF_FRAME], sizeof(sFrame));
        bBusy[iBuf] = true;
        uint16_t usItem = (uint16_t)((iKeep << 8) | iBuf);
        xQueueSend(xClipQueue, &usItem, 0);
        iBuf ^= 1;
        bCapturing = false;
        iRefractory = REFRACTORY_FRAMES;
        iHot = 0;
        iSinceEnd = 0;
      }
      continue;
    }

    if (iWarm < WARMUP_FRAMES) { fFloor += (fRms - fFloor) / (iWarm + 1); iWarm++; continue; }
    if (iRefractory > 0) { iRefractory--; iHot = 0; continue; }

    float fThreshold = fmaxf(TRIG_MIN_RMS, TRIG_FACTOR * fFloor);
    fDbgFloor = fFloor; fDbgThreshold = fThreshold;
    if (fRms > fThreshold) {
      iHot++;
    } else {
      iHot = 0;
      if (fRms < 2.0f * fFloor) fFloor += (fRms - fFloor) / 64.0f;   // slowly follow the background
    }
    if ((iHot >= TRIG_FRAMES || bForce) && iPreCount == PREROLL_FRAMES && !bBusy[iBuf]) {
      for (int i = 0; i < PREROLL_FRAMES; i++) {         // oldest frame first
        const int16_t *psSrc = sPre[(iPreHead + i) % PREROLL_FRAMES];
#if STALE_PREROLL_FIX
        // frames pushed since the last capture ended are fresh; older ones are the tail of the previous word
        if (bHaveBg && iSinceEnd < PREROLL_FRAMES && i < PREROLL_FRAMES - iSinceEnd) psSrc = sBg[i % PAD_SRC_FRAMES];
#endif
        memcpy(&sClip[iBuf][i * VF_FRAME], psSrc, sizeof(sFrame));
      }
      if (!bHaveBg || iSinceEnd >= PREROLL_FRAMES) {      // remember clean background for the next quick word
        memcpy(sBg, &sClip[iBuf][0], sizeof(sBg));
        bHaveBg = true;
      }
      iCaptured = PREROLL_FRAMES;
      iQuiet = 0;
      bCapturing = true;
      bForce = false;
      iHot = 0;
    }
  }
}

// Task 2 (lower priority): features -> model -> LED command; the only task that prints words
void vClassifyTask(void *pvParameters) {
  float fFeat[VF_NUM_FEATURES], fLogit[MODEL_NUM_CLASSES], fProb[MODEL_NUM_CLASSES];
  bool bBlueSelected = false;

  for (;;) {
    uint16_t usItem;
    xQueueReceive(xClipQueue, &usItem, portMAX_DELAY);
    int iBuf = usItem & 0xFF, iKept = usItem >> 8;
    uint32_t ulStart = millis();
    vfExtract(sClip[iBuf], VF_CLIP_SAMPLES, fFeat);

    float fMax = -1e30f;
    for (int c = 0; c < MODEL_NUM_CLASSES; c++) {
      float fSum = kBias[c];
      for (int j = 0; j < MODEL_NUM_FEATURES; j++)
        fSum += kWeights[c][j] * (fFeat[kFeatureIds[j]] - kMean[j]) / kStd[j];
      fLogit[c] = fSum;
      if (fSum > fMax) fMax = fSum;
    }
    float fNorm = 0;
    for (int c = 0; c < MODEL_NUM_CLASSES; c++) { fProb[c] = expf(fLogit[c] - fMax); fNorm += fProb[c]; }
    int iBest = 0;
    for (int c = 0; c < MODEL_NUM_CLASSES; c++) { fProb[c] /= fNorm; if (fProb[c] > fProb[iBest]) iBest = c; }

    const char *pcName = kClassNames[iBest];
    LedCommand_t xCmd = LED_CMD_NONE;
    const char *pcAction = "ignored";
    if (fProb[iBest] < MIN_CONFIDENCE) {
      pcAction = "not sure";
    } else if (!strcmp(pcName, "green")) { bBlueSelected = false; pcAction = "select green"; }
    else if (!strcmp(pcName, "blue"))    { bBlueSelected = true;  pcAction = "select blue"; }
    else if (!strcmp(pcName, "on"))      { xCmd = bBlueSelected ? LED_CMD_BLUE_ON  : LED_CMD_GREEN_ON;  pcAction = bBlueSelected ? "BLUE on"  : "GREEN on"; }
    else if (!strcmp(pcName, "off"))     { xCmd = bBlueSelected ? LED_CMD_BLUE_OFF : LED_CMD_GREEN_OFF; pcAction = bBlueSelected ? "BLUE off" : "GREEN off"; }
    if (xCmd != LED_CMD_NONE) xQueueSend(xLedQueue, &xCmd, 0);

    if (bStream) {                                         // raw window + prediction for tools/live_session.py
      const uint8_t pucHead[8] = {0xA5, 0x5A, 0xA5, 0x5A, (uint8_t)iKept, (uint8_t)iBest, (uint8_t)(fProb[iBest] * 255.0f + 0.5f), 0};
      Serial.write(pucHead, sizeof(pucHead));
      Serial.write((const uint8_t *)sClip[iBuf], sizeof(sClip[iBuf]));
      bBusy[iBuf] = false;
      continue;
    }
    bBusy[iBuf] = false;                                   // features are done; the buffer can be reused
    Serial.print(pcName); Serial.print(" "); Serial.print(fProb[iBest], 2); Serial.print("  [");
    for (int c = 0; c < MODEL_NUM_CLASSES; c++) { Serial.print(kClassNames[c]); Serial.print(" "); Serial.print(fProb[c], 2); Serial.print(c + 1 < MODEL_NUM_CLASSES ? ", " : "]"); }
    Serial.print("  peak_db "); Serial.print(fFeat[2], 1);
    Serial.print("  word "); Serial.print((iKept - PREROLL_FRAMES) * 0.016f, 2); Serial.print(" s");
    Serial.print("  -> "); Serial.print(pcAction);
    Serial.print("  ("); Serial.print(millis() - ulStart); Serial.println(" ms)");
  }
}

// Task 3 (low priority): writes raw frames to USB so a slow host can never stall the audio task
void vRawTask(void *pvParameters) {
  for (;;) {
    if (bRaw && usRawTail != usRawHead) {
      uint16_t usSeq = usRawSeqOf[usRawTail];
      const uint8_t pucHead[6] = {0xA5, 0x5A, 0xA5, 0x5A, (uint8_t)(usSeq & 0xFF), (uint8_t)(usSeq >> 8)};
      Serial.write(pucHead, sizeof(pucHead));
      Serial.write((const uint8_t *)sRaw[usRawTail], sizeof(sRaw[0]));
      usRawTail = (usRawTail + 1) % RAW_RING;
    } else {
      vTaskDelay(pdMS_TO_TICKS(2));
    }
  }
}

void setup() {
  Serial.begin(115200);
  uint32_t ulStart = millis();
  while (!Serial && millis() - ulStart < 2000) delay(10);   // works with or without a USB serial monitor

  vLedInit();
  xClipQueue = xQueueCreate(2, sizeof(uint16_t));
  Serial.print("voice_dsp ready, classes:");
  for (int c = 0; c < MODEL_NUM_CLASSES; c++) { Serial.print(" "); Serial.print(kClassNames[c]); }
  Serial.println("  (stay quiet for 1 s while it learns the background)");

  xTaskCreate(vLedTask,      "led",      128, NULL, 2, NULL);
  xTaskCreate(vAudioTask,    "audio",    384, NULL, 3, NULL);
  xTaskCreate(vClassifyTask, "classify", 512, NULL, 2, NULL);
  xTaskCreate(vRawTask,      "raw",      256, NULL, 1, NULL);
}

void loop() {
  static uint32_t ulLastDebug = 0;
  vTaskDelay(pdMS_TO_TICKS(20));
  while (Serial.available()) {
    int c = Serial.read();
    if (c == 'S') bStream = true;
    else if (c == 'R') { usRawHead = usRawTail = 0; usRawSeq = 0; ulRawDrops = 0; bRaw = true; }
    else if (c == 'T') { bStream = false; bRaw = false; }
    else if (c == 'G') bForce = true;
  }
#if VOICE_DEBUG
  if (!bStream && !bRaw && millis() - ulLastDebug >= 2000) {
    ulLastDebug = millis();
    Serial.print(bMicOk ? "  . background " : "  . MIC FAILED background "); Serial.print(fDbgFloor, 0);
    Serial.print("  loudest frame (2 s) "); Serial.print(fDbgLoudest, 0);
    Serial.print("  trigger above "); Serial.print(fDbgThreshold, 0);
    Serial.print("  frames "); Serial.print(ulDbgFrames); Serial.print(" restarts "); Serial.print(ulDbgRestarts);
    Serial.print("  dc "); Serial.print(fDbgMean, 0);
    Serial.println();
    fDbgLoudest = 0;
  }
#endif
}
