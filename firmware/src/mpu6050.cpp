#include "mpu6050.h"

namespace {
constexpr uint8_t kRegConfig = 0x1A;       // DLPF_CFG in bits 2:0
constexpr uint8_t kRegAccelConfig = 0x1C;  // AFS_SEL in bits 4:3
constexpr uint8_t kRegAccelXoutH = 0x3B;   // ACCEL_XOUT_H .. ACCEL_ZOUT_L (6 bytes)
constexpr uint8_t kRegPwrMgmt1 = 0x6B;
constexpr uint8_t kRegWhoAmI = 0x75;

constexpr uint8_t kPwrWakePllGyroX = 0x01;  // SLEEP=0, CLKSEL=1 (PLL with X gyro ref)
constexpr uint8_t kAccelRange2g = 0x00;
constexpr uint8_t kDlpf44Hz = 0x03;  // accel bandwidth ~44 Hz

constexpr float kLsbPerG = 16384.0f;  // ±2 g
}  // namespace

bool Mpu6050::writeReg(uint8_t reg, uint8_t value) {
  wire_.beginTransmission(addr_);
  wire_.write(reg);
  wire_.write(value);
  return wire_.endTransmission() == 0;
}

bool Mpu6050::readRegs(uint8_t reg, uint8_t* buf, size_t len) {
  wire_.beginTransmission(addr_);
  wire_.write(reg);
  if (wire_.endTransmission(false) != 0) return false;
  if (wire_.requestFrom(addr_, static_cast<uint8_t>(len)) != len) return false;
  for (size_t i = 0; i < len; i++) buf[i] = wire_.read();
  return true;
}

bool Mpu6050::readWhoAmI(uint8_t& value) { return readRegs(kRegWhoAmI, &value, 1); }

bool Mpu6050::configure() {
  bool ok = writeReg(kRegPwrMgmt1, kPwrWakePllGyroX);
  ok &= writeReg(kRegAccelConfig, kAccelRange2g);
  ok &= writeReg(kRegConfig, kDlpf44Hz);
  return ok;
}

bool Mpu6050::readAccel(float& ax, float& ay, float& az) {
  uint8_t b[6];
  if (!readRegs(kRegAccelXoutH, b, sizeof(b))) return false;
  ax = static_cast<int16_t>((b[0] << 8) | b[1]) / kLsbPerG;
  ay = static_cast<int16_t>((b[2] << 8) | b[3]) / kLsbPerG;
  az = static_cast<int16_t>((b[4] << 8) | b[5]) / kLsbPerG;
  return true;
}
