#include <Arduino.h>
#include <FreeRTOS.h>
#include <task.h>
#include <queue.h>
#include <semphr.h>
#include <LSM6DS3.h>
#include <Wire.h>

// FreeRTOS naming: v = returns void, x = BaseType_t/handle, f = float,
// pv = void pointer, prv = private (static) to this file.

SemaphoreHandle_t xButtonSemaphore;
SemaphoreHandle_t xSerialMutex;
QueueHandle_t     xTempQueue;

LSM6DS3 imu(I2C_MODE, 0x6A);

// Safe print: only one task writes to Serial at a time
static void prvSafePrint(const char *pcMessage) {
  xSemaphoreTake(xSerialMutex, portMAX_DELAY);
  Serial.println(pcMessage);
  xSemaphoreGive(xSerialMutex);
}

// ISR: release the semaphore, nothing else
static void prvButtonISR() {
  BaseType_t xHigherPriorityTaskWoken = pdFALSE;
  xSemaphoreGiveFromISR(xButtonSemaphore, &xHigherPriorityTaskWoken);
  portYIELD_FROM_ISR(xHigherPriorityTaskWoken);   // switch to the waiting task now
}

// Task 1: blink forever (low priority)
void vBlinkTask(void *pvParameters) {
  for (;;) {
    digitalWrite(LED_GREEN, !digitalRead(LED_GREEN));
    vTaskDelay(pdMS_TO_TICKS(500));
  }
}

// Task 2: sleeps until the button ISR wakes it (higher priority)
void vButtonTask(void *pvParameters) {
  for (;;) {
    xSemaphoreTake(xButtonSemaphore, portMAX_DELAY);   // blocks, uses no CPU
    digitalWrite(LED_BLUE, !digitalRead(LED_BLUE));
    prvSafePrint("Button pressed");
    vTaskDelay(pdMS_TO_TICKS(50));                     // debounce
    xSemaphoreTake(xButtonSemaphore, 0);               // discard bounces
  }
}

// Task 3: produces a value every second and sends it through a queue
void vTempTask(void *pvParameters) {
  for (;;) {
    float fTemp = 25.0f;                               // replace with the real reading
    xQueueSend(xTempQueue, &fTemp, 0);
    vTaskDelay(pdMS_TO_TICKS(1000));
  }
}

// Task 4: owns serial reporting
void vReportTask(void *pvParameters) {
  float fTemp;
  for (;;) {
    if (xQueueReceive(xTempQueue, &fTemp, portMAX_DELAY) == pdTRUE) {
      xSemaphoreTake(xSerialMutex, portMAX_DELAY);
      Serial.print("Temp: "); Serial.println(fTemp);
      xSemaphoreGive(xSerialMutex);
    }
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);
  pinMode(D1, INPUT_PULLUP);

  xButtonSemaphore = xSemaphoreCreateBinary();
  xSerialMutex     = xSemaphoreCreateMutex();
  xTempQueue       = xQueueCreate(8, sizeof(float));

  attachInterrupt(digitalPinToInterrupt(D1), prvButtonISR, FALLING);

  //          function                 name             stack(words)               params              priority handle
  xTaskCreate(vBlinkTask,  "blink",  128,         NULL,  1,       NULL);
  xTaskCreate(vButtonTask, "button", 256,         NULL,  3,       NULL);
  xTaskCreate(vTempTask,   "temp",   128,         NULL,  2,       NULL);
  xTaskCreate(vReportTask, "report", 512,         NULL,  2,       NULL);
}

// setup()/loop() keep their Arduino names: the core calls them by name
void loop() {
  vTaskDelay(pdMS_TO_TICKS(1000));   // idle; the tasks do the work
}
