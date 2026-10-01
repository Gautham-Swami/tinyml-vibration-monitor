#include "commands.h"

#include <ctype.h>
#include <stdlib.h>
#include <string.h>

namespace {
// Copies line into out, trimmed and upper-cased. out must hold LineBuffer::kCapacity + 1.
void normalize(const char* line, char* out) {
  while (isspace(static_cast<unsigned char>(*line))) line++;
  size_t n = 0;
  while (line[n] != '\0' && n < LineBuffer::kCapacity) {
    out[n] = static_cast<char>(toupper(static_cast<unsigned char>(line[n])));
    n++;
  }
  while (n > 0 && isspace(static_cast<unsigned char>(out[n - 1]))) n--;
  out[n] = '\0';
}

bool parseRate(const char* arg, int& rateHz) {
  while (isspace(static_cast<unsigned char>(*arg))) arg++;
  if (*arg == '\0') return false;
  char* end = nullptr;
  long v = strtol(arg, &end, 10);
  if (*end != '\0') return false;
  if (v < kMinRateHz || v > kMaxRateHz) return false;
  rateHz = static_cast<int>(v);
  return true;
}
}  // namespace

Command parseCommand(const char* line) {
  char s[LineBuffer::kCapacity + 1];
  normalize(line, s);

  if (strcmp(s, "PING") == 0) return {CommandType::Ping, 0};
  if (strcmp(s, "STREAM ON") == 0) return {CommandType::StreamOn, 0};
  if (strcmp(s, "STREAM OFF") == 0) return {CommandType::StreamOff, 0};
  if (strncmp(s, "RATE", 4) == 0 && (s[4] == '\0' || isspace(static_cast<unsigned char>(s[4])))) {
    int rate = 0;
    if (parseRate(s + 4, rate)) return {CommandType::Rate, rate};
    return {CommandType::RateInvalid, 0};
  }
  return {CommandType::Unknown, 0};
}

bool LineBuffer::push(char c) {
  if (c == '\r') return false;
  if (c == '\n') {
    bool complete = !overflow_;
    buf_[len_] = '\0';
    len_ = 0;
    overflow_ = false;
    return complete;
  }
  if (overflow_) return false;
  if (len_ >= kCapacity) {
    overflow_ = true;
    return false;
  }
  buf_[len_++] = c;
  return false;
}
