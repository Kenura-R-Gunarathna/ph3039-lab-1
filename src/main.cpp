#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "fmt.h"

// DS18B20 data line
#define ONE_WIRE_BUS 2

// Onewire Bus protocol definition:
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

void setup(void) {
  Serial.begin(9600);
  csvln("time_ms,temp_c,temp_k");  // CSV header

  // Start the onewire bus protocol:
  sensors.begin();
}

void loop(void) {
  // Send command to all sensors on the onewire bus to take a temperature measurement
  sensors.requestTemperatures(); 

  // Onewire Bus index assignment: 
  float tempC = sensors.getTempCByIndex(0);
  float tempK = tempC + 273.15;

  if (tempC != DEVICE_DISCONNECTED_C) {
    csvln("{},{},{}", millis(), tempC, tempK);
  } else {
    csvln("{},,", millis());  // null row keeps the CSV aligned
    logln("Error: could not read temperature, check wiring");
  }

  delay(1000);
}