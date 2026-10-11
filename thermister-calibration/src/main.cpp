#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "fmt.h"

// DS18B20 data line
#define ONE_WIRE_BUS 2

// NTC thermistor (voltage divider midpoint)
constexpr uint8_t THERMISTOR_PIN = A2;

// Onewire Bus protocol definition:
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

void setup(void) {
  Serial.begin(9600);
  csvln("time_ms,temp_c,temp_k,adc");  // CSV header

  // Start the onewire bus protocol:
  sensors.begin();
}

void loop(void) {
  // Send command to all sensors on the onewire bus to take a temperature measurement
  sensors.requestTemperatures(); 

  // Onewire Bus index assignment: 
  float tempC = sensors.getTempCByIndex(0);
  float tempK = tempC + 273.15;

  // Raw 10-bit ADC reading
  int adc = analogRead(THERMISTOR_PIN);

  if (tempC != DEVICE_DISCONNECTED_C) {
    csvln("{},{},{},{}", millis(), tempC, tempK, adc);
  } else {
    csvln("{},,,{}", millis(), adc);  // DS18B20 fields null, ADC still valid
    logln("Error: could not read temperature, check wiring");
  }

  delay(1000);
}