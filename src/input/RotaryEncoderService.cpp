#include "RotaryEncoderService.h"

#include "../config/AppConfig.h"

namespace {
// Index: previous CLK/DT state followed by the current CLK/DT state.
// Impossible two-bit jumps produce zero; valid reverse transitions cancel bounce.
constexpr int8_t transitionDeltas[16] = {
    0, -1, 1, 0,
    1, 0, 0, -1,
    -1, 0, 0, 1,
    0, 1, -1, 0};
}

void RotaryEncoderService::begin() {
  pinMode(AppConfig::Input::rotaryEncoderClockPin, INPUT_PULLUP);
  pinMode(AppConfig::Input::rotaryEncoderDataPin, INPUT_PULLUP);
  // Reserved for a future feature. It intentionally produces no action.
  pinMode(AppConfig::Input::rotaryEncoderSwitchPin, INPUT_PULLUP);

  previousState_ = readState();
  accumulatedTransitions_ = 0;
  started_ = true;
}

InputAction RotaryEncoderService::update() {
  if (!started_) {
    return InputAction::None;
  }

  const uint8_t currentState = readState();
  if (currentState == previousState_) {
    return InputAction::None;
  }

  const uint8_t transition = (previousState_ << 2) | currentState;
  const int8_t delta = transitionDeltas[transition];
  previousState_ = currentState;

  if (delta == 0) {
    // Do not combine partial movement across an invalid quadrature jump.
    accumulatedTransitions_ = 0;
    return InputAction::None;
  }

  accumulatedTransitions_ += delta;
  if (accumulatedTransitions_ <
          AppConfig::Input::rotaryEncoderTransitionsPerStep &&
      accumulatedTransitions_ >
          -AppConfig::Input::rotaryEncoderTransitionsPerStep) {
    return InputAction::None;
  }

  const bool positiveDirection = accumulatedTransitions_ > 0;
  accumulatedTransitions_ = 0;
  const bool nextPage =
      positiveDirection != AppConfig::Input::rotaryEncoderInvertDirection;
  return nextPage ? InputAction::NextPage : InputAction::PreviousPage;
}

uint8_t RotaryEncoderService::readState() const {
  const uint8_t clockState =
      digitalRead(AppConfig::Input::rotaryEncoderClockPin) == HIGH ? 1 : 0;
  const uint8_t dataState =
      digitalRead(AppConfig::Input::rotaryEncoderDataPin) == HIGH ? 1 : 0;
  return (clockState << 1) | dataState;
}
