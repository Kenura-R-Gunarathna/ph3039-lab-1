#include <Arduino.h>
#include <FreeRTOS.h>
#include <task.h>
#include <queue.h>
#include <semphr.h>
#include <LSM6DS3.h>
#include <Wire.h>

SemaphoreHandle_t buttonSem;
SemaphoreHandle_t serialMutex;
QueueHandle_t     tempQ;

LSM6DS3 imu(I2C_MODE, 0x6A);

// Safe print: only one task writes to Serial at a time
void say(const char* msg) {
  xSemaphoreTake(serialMutex, portMAX_DELAY);
  Serial.println(msg);
  xSemaphoreGive(serialMutex);
}

// ISR: release the semaphore, nothing else
void buttonIsr() {
  BaseType_t woken = pdFALSE;
  xSemaphoreGiveFromISR(buttonSem, &woken);
  portYIELD_FROM_ISR(woken);              // switch to the waiting task now
}

// Task 1: blink forever (low priority)
void blinkTask(void*) {
  for (;;) {
    digitalWrite(LED_GREEN, !digitalRead(LED_GREEN));
    vTaskDelay(pdMS_TO_TICKS(500));
  }
}
// Task 2: sleeps until the button ISR wakes it (higher priority)
void buttonTask(void*) {
  for (;;) {
    xSemaphoreTake(buttonSem, portMAX_DELAY);   // blocks, uses no CPU
    digitalWrite(LED_BLUE, !digitalRead(LED_BLUE));
    say("Button pressed");
    vTaskDelay(pdMS_TO_TICKS(50));              // debounce
    xSemaphoreTake(buttonSem, 0);               // discard bounces
  }
}

// Task 3: produces a value every second and sends it through a queue
void tempTask(void*) {
  for (;;) {
    float t = 25.0f;                            // replace with the real reading
    xQueueSend(tempQ, &t, 0);
    vTaskDelay(pdMS_TO_TICKS(1000));
  }
}

// Task 4: owns serial reporting
void reportTask(void*) {
  float t;
  for (;;) {
    if (xQueueReceive(tempQ, &t, portMAX_DELAY) == pdTRUE) {
      xSemaphoreTake(serialMutex, portMAX_DELAY);
      Serial.print("Temp: "); Serial.println(t);
      xSemaphoreGive(serialMutex);
    }
  }
}
void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);
  pinMode(D1, INPUT_PULLUP);

  buttonSem   = xSemaphoreCreateBinary();
  serialMutex = xSemaphoreCreateMutex();
  tempQ       = xQueueCreate(8, sizeof(float));

  attachInterrupt(digitalPinToInterrupt(D1), buttonIsr, FALLING);

  //            function    name     stack(words) arg   priority handle
  xTaskCreate(blinkTask,  "blink",  128,  NULL, 1, NULL);
  xTaskCreate(buttonTask, "button", 256,  NULL, 3, NULL);
  xTaskCreate(tempTask,   "temp",   128,  NULL, 2, NULL);
  xTaskCreate(reportTask, "report", 512,  NULL, 2, NULL);
}

void loop() {
  vTaskDelay(pdMS_TO_TICKS(1000));   // idle; the tasks do the work
}