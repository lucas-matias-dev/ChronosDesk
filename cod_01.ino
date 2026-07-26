#include "src/app/AppController.h"

AppController application;

void setup() {
  application.begin();
}

void loop() {
  application.update();
}
