#include "led_control.h"
#include <task.h>

QueueHandle_t xLedQueue;

void vLedInit() {
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);
  digitalWrite(LED_GREEN, HIGH);       // XIAO LEDs are active-low: HIGH = off
  digitalWrite(LED_BLUE, HIGH);
  xLedQueue = xQueueCreate(4, sizeof(LedCommand_t));
}

void vLedTask(void *pvParameters) {
  LedCommand_t xCmd;
  for (;;) {
    if (xQueueReceive(xLedQueue, &xCmd, portMAX_DELAY) == pdTRUE) {
      switch (xCmd) {
        case LED_CMD_GREEN_ON:  digitalWrite(LED_GREEN, LOW);  break;
        case LED_CMD_GREEN_OFF: digitalWrite(LED_GREEN, HIGH); break;
        case LED_CMD_BLUE_ON:   digitalWrite(LED_BLUE, LOW);   break;
        case LED_CMD_BLUE_OFF:  digitalWrite(LED_BLUE, HIGH);  break;
        default: break;
      }
    }
  }
}
