# Notes on the `arduino/` code:

## Directory Structure

- `test/` contains test sketches you can upload to the Arduino Uno to test motor and servo movement separately.
  - These tests hard-code sequences of motor and servo movement, while the tests in `computer/motors/` and `computer/servos/` prompt you to enter motor directions and speed and servo angles of your choice, sending them over WiFi from the computer to the ESP32-WROVER, which forwards them to the Arduino, which finally sends them to the L298N (which sends them to the motors) or the SG-90s.
- `production.ino` is the code to be run by the the Arduino in production.

## Arduino Setup

- Remember to unplug the Rx cable before uploading any of these sketches (and replug it after uploading).

## Comments

- Due to friction and robot weight, speeds below 135 do not generate enough torque to move the robot (but it may be slightly different for yours).
- `DOWN_ANGLE`, `UP_ANGLE`, `VERT_CENTER_ANGLE`, `LEFT_ANGLE`, `RIGHT_ANGLE`, `HORIZ_CENTER_ANGLE` might also be different for your robot, e.g.
  `const int DOWN_ANGLE = 50;`
  defines the minimum angle for the up-down servo not to collide with the ESP32-CAMs.
