#pragma once

#include <Arduino.h>

enum class InputAction : uint8_t {
  None,
  NextPage,
  PreviousPage
};

class RotaryEncoderService {
 public:
  void begin();
  InputAction update();

 private:
  uint8_t readState() const;

  uint8_t previousState_ = 0;
  int8_t accumulatedTransitions_ = 0;
  bool started_ = false;
};
