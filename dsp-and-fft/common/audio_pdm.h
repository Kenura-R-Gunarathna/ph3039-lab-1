#pragma once
#include <stdint.h>
#include <stddef.h>

// Thin wrapper over the on-board PDM mic (16 kHz, mono, 16-bit).
#define AUDIO_SAMPLE_RATE 16000

bool   xAudioBegin();                                   // start the mic
size_t xAudioRead(int16_t *psBuffer, size_t xSamples);  // non-blocking, returns samples copied

// NOTE: the PDM driver shuts the mic off for good if the reader falls behind (it overflows its
// 512-byte buffer). Keep calling xAudioRead() at least every ~10 ms while the mic is running,
// or stop it with xAudioEnd() and start it again later with xAudioBegin().
void   vAudioEnd();
