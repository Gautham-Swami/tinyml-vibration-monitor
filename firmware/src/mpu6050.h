#pragma once

#include <Arduino.h>
#include <Wire.h>

// Minimal raw-register MPU-6050 driver: accelerometer only, ±2 g range.
class Mpu6050 {
 public:
  static constexpr uint8_t kExpectedWhoAmI = 0x68;

  explicit Mpu6050(TwoWire& wire, uint8_t addr = 0x68) : wire_(wire), addr_(addr) {}

  // Reads WHO_AM_I (0x75). Returns false if the device didn't respond.
  bool readWhoAmI(uint8_t& value);

  // Wakes the sensor and sets ±2 g range and ~44 Hz DLPF.
  // Returns false if any register write failed.
  bool configure();

  // Burst-reads the accelerometer and converts to g. Returns false on I2C error.
  bool readAccel(float& ax, float& ay, float& az);

  uint8_t address() const { return addr_; }

 private:
  bool writeReg(uint8_t reg, uint8_t value);
  bool readRegs(uint8_t reg, uint8_t* buf, size_t len);

  TwoWire& wire_;
  uint8_t addr_;
};
