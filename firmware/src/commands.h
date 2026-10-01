#pragma once

#include <stddef.h>

// Serial command handling. Pure logic (no Arduino calls) so it can be unit
// tested in a PlatformIO native env later.

constexpr int kMinRateHz = 10;
constexpr int kMaxRateHz = 200;

enum class CommandType { Ping, Rate, RateInvalid, StreamOn, StreamOff, Unknown };

struct Command {
  CommandType type;
  int rateHz;  // valid only when type == Rate
};

// Parses one line (without the newline). Case-insensitive, surrounding
// whitespace ignored.
Command parseCommand(const char* line);

// Accumulates characters into lines. CR is ignored; LF ends a line. A line
// longer than the buffer is discarded whole.
class LineBuffer {
 public:
  static constexpr size_t kCapacity = 32;

  // Returns true when c completes a line; the line is then available via line()
  // until the next push().
  bool push(char c);
  const char* line() const { return buf_; }

 private:
  char buf_[kCapacity + 1] = {};
  size_t len_ = 0;
  bool overflow_ = false;
};
