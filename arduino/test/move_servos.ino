// ##########################################
// Test sketch for Arduino to control SG90s #
// ##########################################
// Flash this sketch to the Uno, then after testing, flash: production.ino

// takes care of mapping servo.write(angle) into correct pulse sequence for servo
#include <Servo.h>

// ###############
// Configuration #
// ###############

// Arduino - SG90s connection pins
const int ARDUINO_UP_DOWN = 9;         // 1st SG90 (vertical eye movement)
const int ARDUINO_LEFT_RIGHT = A0;     // 2nd SG90 (horizontal eye movement)

// Angle limits (due to eye movement mechanism design) and center positions
const int DOWN_ANGLE = 50;             // Lowest vertical position, i.e., look down (degrees)
const int UP_ANGLE = 110;              // Highest vertical position, i.e., look up (degrees)
const int VERT_CENTER_ANGLE = 80;      // Vertical center position, i.e., look vertically forward (degrees)
const int LEFT_ANGLE = 120;            // Leftmost position, i.e., look left (degrees)
const int RIGHT_ANGLE = 60;            // Rightmost position, i.e., look right (degrees)
const int HORIZ_CENTER_ANGLE = 90;     // Horizontal center position, i.e., look horizontally forward (degrees)

// Movement duration via delay until next movement (in milliseconds)
const int DELAY_TIME = 400;

// Number of times to repeat each movement pattern (e.g., left to right)
const int NUM_ITERATIONS = 3;

// Servo objects
Servo up_down_servo;
Servo left_right_servo;

// Vertical movement positions -because in this test sketch we only move from end of range to 
// end of range, e.g., from up to down but not to somewhere in between, other than the vertical center
enum VerticalDirection { 
   UP,
   DOWN,
   VERT_CENTER
};

// Horizontal movement positions
enum HorizontalDirection { 
   LEFT,
   RIGHT,
   HORIZ_CENTER
};

// #######################################################################
// Helper 1: Convert vertical direction from enum to corresponding angle #
// #######################################################################
int getVerticalAngle(VerticalDirection dir) {
   switch(dir) {
       case UP: return UP_ANGLE;
       case DOWN: return DOWN_ANGLE;
       case VERT_CENTER: return VERT_CENTER_ANGLE;
       default: return VERT_CENTER_ANGLE;
   }
}

// #########################################################################
// Helper 2: Convert horizontal direction from enum to corresponding angle #
// #########################################################################
int getHorizontalAngle(HorizontalDirection dir) {
   switch(dir) {
       case LEFT: return LEFT_ANGLE;
       case RIGHT: return RIGHT_ANGLE;
       case HORIZ_CENTER: return HORIZ_CENTER_ANGLE;
       default: return HORIZ_CENTER_ANGLE;
   }
}

// ###################################################
// Helper 3: Move both servos to specified positions #
// ###################################################
void moveServos(VerticalDirection vertDir, HorizontalDirection horizDir) {
   int vertAngle = getVerticalAngle(vertDir);
   int horizAngle = getHorizontalAngle(horizDir);
   
   // since we move both servos we allow diagonal movement (e.g., down and left, up and right, etc.)
   up_down_servo.write(vertAngle);
   left_right_servo.write(horizAngle);
   delay(DELAY_TIME);
}

// ##############################################
// Helper 4: Center vertically and horizontally #
// ##############################################
void centerServos() {
   moveServos(VERT_CENTER, HORIZ_CENTER);
}

// #############################################################
// Helper 5: Initialize servos by attaching and centering them #
// #############################################################
void initializeServos() {
   // attach each Arduino pin (for a servo) to servo object
   up_down_servo.attach(ARDUINO_UP_DOWN);
   left_right_servo.attach(ARDUINO_LEFT_RIGHT);

   // center
   centerServos();
}

// ##########################################################
// Helper 6: Test sequence one: left-right movement pattern #
// ##########################################################
void moveLeftRight() {
   // move left to right while keeping the vertical center
   for (int i = 0; i < NUM_ITERATIONS; i++) {
       moveServos(VERT_CENTER, LEFT);
       moveServos(VERT_CENTER, RIGHT);
   }
   // re-center
   centerServos();
}

// #######################################################
// Helper 7: Test sequence two: up-down movement pattern #
// #######################################################
void moveUpDown() {
   // move up to down while keeping the horizontal center
   for (int i = 0; i < NUM_ITERATIONS; i++) {
       moveServos(UP, HORIZ_CENTER);
       moveServos(DOWN, HORIZ_CENTER);
   }
   // re-center
   centerServos();
}

// ##########################################################################
// Helper 8: Test sequence three: top-left to bottom-right movement pattern #
// ##########################################################################
void moveDiagonalTopLeftBottomRight() {
   for (int i = 0; i < NUM_ITERATIONS; i++) {
       moveServos(UP, LEFT);
       moveServos(DOWN, RIGHT);
   }
   // re-center
   centerServos();
}

// #########################################################################
// Helper 9: Test sequence four: top-right to bottom-left movement pattern #
// #########################################################################
void moveDiagonalTopRightBottomLeft() {
   for (int i = 0; i < NUM_ITERATIONS; i++) {
       moveServos(UP, RIGHT);
       moveServos(DOWN, LEFT);
   }
   // re-center
   centerServos();
}

// ###################################################################
// Setup: Initialize pins and execute test sequence (runs only once) #
// ###################################################################
void setup() {
   // initialize
   initializeServos();

   // test
   moveLeftRight();
   moveUpDown();
   moveDiagonalTopLeftBottomRight();
   moveDiagonalTopRightBottomLeft();
}

// ##########################################################
// Loop: Do nothing after setup (avoids test sequence loop) #
// ##########################################################
void loop() {
}