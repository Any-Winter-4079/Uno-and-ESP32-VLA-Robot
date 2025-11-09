// ##########################################
// Test sketch for Arduino to control L298N #
// ##########################################
// Flash this sketch to the Uno, then after testing, flash: production.ino

// ###############
// Configuration #
// ###############

// Arduino - L298N connection pins
const int ARDUINO_RIGHT_MOTOR_SPEED = 6;  // ENA on L298N - Enable pin (right motor)
const int ARDUINO_RIGHT_MOTOR_DIR1 = 8;   // IN1 on L298N - Direction 1 (right motor)
const int ARDUINO_RIGHT_MOTOR_DIR2 = 7;   // IN2 on L298N - Direction 2 (right motor)
const int ARDUINO_LEFT_MOTOR_SPEED = 3;   // ENB on L298N - Enable pin (left motor)
const int ARDUINO_LEFT_MOTOR_DIR1 = 5;    // IN3 on L298N - Direction 1 (left motor)
const int ARDUINO_LEFT_MOTOR_DIR2 = 4;    // IN4 on L298N - Direction 2 (left motor)

// PWM speed values
const int MAX_SPEED = 255;                // Max speed (100% duty cycle)
// below this value, this robot does not advance due to weight and friction!
const int MIN_USABLE_SPEED = 135;         // ~53% speed
const int REAL_STOP_SPEED = 0;            // Stopped (0% duty cycle)

// Movement duration via delay until next movement (in milliseconds)
const int SHORT_DURATION = 500;
const int MEDIUM_DURATION = 2000;
const int LONG_DURATION = 3000;

// Motor advance direction
enum Direction {
   FORWARD,
   BACKWARD
};

// Motor turn direction
enum Turn {
   LEFT,
   RIGHT
};

// #######################################################################
// Helper 1: Initialize motors pins by setting their pin modes to OUTPUT #
// #######################################################################
void initializeMotorsPins() {
   // right motor
   pinMode(ARDUINO_RIGHT_MOTOR_SPEED, OUTPUT);
   pinMode(ARDUINO_RIGHT_MOTOR_DIR1, OUTPUT);
   pinMode(ARDUINO_RIGHT_MOTOR_DIR2, OUTPUT);
   // left motor
   pinMode(ARDUINO_LEFT_MOTOR_SPEED, OUTPUT);
   pinMode(ARDUINO_LEFT_MOTOR_DIR1, OUTPUT);
   pinMode(ARDUINO_LEFT_MOTOR_DIR2, OUTPUT);
}

// ###############################
// Helper 2: Set motor direction #
// ###############################
void setMotorDirection(int motor_dir1, int motor_dir2, Direction direction) {
   // forward movement: right motor (10, move forward), left motor (10, move forward)
   // backward movement: right motor (01, move backward), left motor (01, move backward)
   digitalWrite(motor_dir1, direction == FORWARD ? HIGH : LOW);
   digitalWrite(motor_dir2, direction == FORWARD ? LOW : HIGH);
}

// ###########################
// Helper 3: Set motor speed #
// ###########################
void setMotorSpeed(int motorSpeedPin, int speed) {
   analogWrite(motorSpeedPin, constrain(speed, 0, 255));
}

// ###################
// Helper 4: Advance #
// ###################
void advance(Direction direction, int speed, int duration) {
   // advance forward or backward
   setMotorDirection(ARDUINO_RIGHT_MOTOR_DIR1, ARDUINO_RIGHT_MOTOR_DIR2, direction);
   setMotorDirection(ARDUINO_LEFT_MOTOR_DIR1, ARDUINO_LEFT_MOTOR_DIR2, direction);
   setMotorSpeed(ARDUINO_RIGHT_MOTOR_SPEED, speed);
   setMotorSpeed(ARDUINO_LEFT_MOTOR_SPEED, speed);
   delay(duration);
}

// ################
// Helper 5: Turn #
// ################
void turn(Turn turnDirection, int speed, int duration) {
   // set motors to their rotation directions depending on turn
   // right turn: right motor (01, move backward), left motor (10, move forward)
   // left turn: right motor (10, move forward), left motor (01, move backward)
   Direction rightMotorDir = (turnDirection == LEFT) ? FORWARD : BACKWARD;
   Direction leftMotorDir = (turnDirection == LEFT) ? BACKWARD : FORWARD;

   setMotorDirection(ARDUINO_RIGHT_MOTOR_DIR1, ARDUINO_RIGHT_MOTOR_DIR2, rightMotorDir);
   setMotorDirection(ARDUINO_LEFT_MOTOR_DIR1, ARDUINO_LEFT_MOTOR_DIR2, leftMotorDir);
   setMotorSpeed(ARDUINO_RIGHT_MOTOR_SPEED, speed);
   setMotorSpeed(ARDUINO_LEFT_MOTOR_SPEED, speed);
   delay(duration);
}

// ################
// Helper 6: Stop #
// ################
void stop(int duration) {
   setMotorSpeed(ARDUINO_RIGHT_MOTOR_SPEED, REAL_STOP_SPEED);
   setMotorSpeed(ARDUINO_LEFT_MOTOR_SPEED, REAL_STOP_SPEED);
   delay(duration);
}

// ###################################################################
// Setup: Initialize pins and execute test sequence (runs only once) #
// ###################################################################
void setup() {
   // initialize
   initializeMotorsPins();

   // test
   advance(FORWARD, MIN_USABLE_SPEED, MEDIUM_DURATION);
   advance(BACKWARD, MIN_USABLE_SPEED, MEDIUM_DURATION);
   turn(LEFT, MAX_SPEED, LONG_DURATION);
   stop(MEDIUM_DURATION);
   turn(RIGHT, MAX_SPEED, LONG_DURATION);
   stop(MEDIUM_DURATION);
}

// ##########################################################
// Loop: Do nothing after setup (avoids test sequence loop) #
// ##########################################################
void loop() {
}