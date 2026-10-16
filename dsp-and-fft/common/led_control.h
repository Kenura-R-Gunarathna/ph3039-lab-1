#pragma once
#include <Arduino.h>
#include <FreeRTOS.h>
#include <queue.h>

// Shared by every voice approach: the recogniser sends a command, vLedTask obeys it.
typedef enum {
  LED_CMD_NONE = 0,
  LED_CMD_GREEN_ON,
  LED_CMD_GREEN_OFF,
  LED_CMD_BLUE_ON,
  LED_CMD_BLUE_OFF,
} LedCommand_t;

// Older single-LED names (the TFLM / Edge Impulse stubs) mean the green LED.
#define LED_CMD_ON  LED_CMD_GREEN_ON
#define LED_CMD_OFF LED_CMD_GREEN_OFF

extern QueueHandle_t xLedQueue;

void vLedInit();                       // pinMode both LEDs (off) + create xLedQueue (call from setup)
void vLedTask(void *pvParameters);     // blocks on xLedQueue, drives LED_GREEN / LED_BLUE
