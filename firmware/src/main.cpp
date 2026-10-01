// Streams MPU-6050 accelerometer samples over serial as CSV: t_ms,ax,ay,az (g).
// A hardware timer paces sampling; the ISR only flags that a sample is due and
// loop() does the I2C read and printing.

#include <Arduino.h>
#include <Wire.h>

#include "commands.h"
#include "mpu6050.h"

namespace {
constexpr int kSdaPin = 21;
constexpr int kSclPin = 22;
constexpr uint32_t kI2cHz = 400000;
constexpr uint32_t kBaud = 115200;
constexpr int kDefaultRateHz = 100;
constexpr uint32_t kTimerTickHz = 1000000;  // 80 MHz APB / 80

Mpu6050 imu(Wire);
LineBuffer lineBuf;
hw_timer_t* timer = nullptr;
portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;

// Shared with the ISR; guarded by timerMux.
volatile bool samplePending = false;
volatile uint32_t sampleTimeMs = 0;
volatile uint32_t overruns = 0;

bool streaming = true;
uint32_t readErrors = 0;

void IRAM_ATTR onTimer() {
  portENTER_CRITICAL_ISR(&timerMux);
  if (samplePending) overruns++;
  sampleTimeMs = millis();
  samplePending = true;
  portEXIT_CRITICAL_ISR(&timerMux);
}

void setRate(int rateHz) {
  timerAlarmWrite(timer, kTimerTickHz / rateHz, true);
  // Restart the count so a shorter period can't leave the counter past the new alarm.
  timerWrite(timer, 0);
}

void reportErrorCounts() {
  portENTER_CRITICAL(&timerMux);
  uint32_t o = overruns;
  overruns = 0;
  portEXIT_CRITICAL(&timerMux);
  if (o > 0 || readErrors > 0) {
    Serial.printf("# overruns=%lu read_errors=%lu\n", static_cast<unsigned long>(o),
                  static_cast<unsigned long>(readErrors));
  }
  readErrors = 0;
}

void handleCommand(const Command& cmd) {
  switch (cmd.type) {
    case CommandType::Ping:
      Serial.println("PONG");
      break;
    case CommandType::Rate:
      setRate(cmd.rateHz);
      Serial.printf("OK RATE %d\n", cmd.rateHz);
      break;
    case CommandType::RateInvalid:
      Serial.printf("ERR RATE %d-%d\n", kMinRateHz, kMaxRateHz);
      break;
    case CommandType::StreamOn:
      streaming = true;
      Serial.println("OK STREAM ON");
      break;
    case CommandType::StreamOff:
      streaming = false;
      Serial.println("OK STREAM OFF");
      reportErrorCounts();
      break;
    case CommandType::Unknown:
      Serial.println("ERR UNKNOWN");
      break;
  }
}

void pollSerial() {
  while (Serial.available() > 0) {
    if (lineBuf.push(static_cast<char>(Serial.read()))) {
      handleCommand(parseCommand(lineBuf.line()));
    }
  }
}

void initImu() {
  uint8_t whoAmI = 0;
  if (!imu.readWhoAmI(whoAmI)) {
    Serial.printf("# ERR no response at 0x%02X\n", imu.address());
  } else {
    Serial.printf("# WHO_AM_I=0x%02X\n", whoAmI);
    if (whoAmI != Mpu6050::kExpectedWhoAmI) {
      Serial.printf("# WARN WHO_AM_I=0x%02X, expected 0x%02X (clone?)\n", whoAmI,
                    Mpu6050::kExpectedWhoAmI);
    }
  }
  if (!imu.configure()) {
    Serial.println("# ERR MPU-6050 config write failed");
  }
}
}  // namespace

void setup() {
  Serial.begin(kBaud);
  Wire.begin(kSdaPin, kSclPin, kI2cHz);

  Serial.println("# tinyml-vibration-monitor imu-stream");
  initImu();
  Serial.printf("# rate=%d Hz, range=+-2g\n", kDefaultRateHz);
  Serial.println("# t_ms,ax,ay,az");

  timer = timerBegin(0, 80, true);
  timerAttachInterrupt(timer, &onTimer, true);
  timerAlarmWrite(timer, kTimerTickHz / kDefaultRateHz, true);
  timerAlarmEnable(timer);
}

void loop() {
  pollSerial();

  portENTER_CRITICAL(&timerMux);
  bool pending = samplePending;
  uint32_t t = sampleTimeMs;
  samplePending = false;
  portEXIT_CRITICAL(&timerMux);

  if (!pending || !streaming) return;

  float ax, ay, az;
  if (!imu.readAccel(ax, ay, az)) {
    readErrors++;
    return;
  }
  char line[48];
  int n = snprintf(line, sizeof(line), "%lu,%.4f,%.4f,%.4f\n", static_cast<unsigned long>(t), ax,
                   ay, az);
  Serial.write(reinterpret_cast<const uint8_t*>(line), n);
}
