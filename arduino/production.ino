// ##########################################################
// Production sketch for Arduino to control L298N and SG90s #
// ##########################################################

// takes care of mapping servo.write(angle) into correct pulse sequence for servo
#include <Servo.h>
// takes care of I2C bus for talking to OLED display
#include <Wire.h>
// takes care of graphics primitives (lines, shapes, text)
#include <Adafruit_GFX.h>
// takes care of SSD1306 OLED display driver
#include <Adafruit_SSD1306.h>
// takes care of FreeMono 9 pt bitmap font for OLED display text
#include <Fonts/FreeMono9pt7b.h>

// ###############
// Configuration #
// ###############

// Arduino - L298N connection pins
const int ARDUINO_RIGHT_MOTOR_SPEED = 6;    // ENA on L298N - Enable pin (right motor)
const int ARDUINO_RIGHT_MOTOR_DIR1 = 8;     // IN1 on L298N - Direction 1 (right motor)
const int ARDUINO_RIGHT_MOTOR_DIR2 = 7;     // IN2 on L298N - Direction 2 (right motor)
const int ARDUINO_LEFT_MOTOR_SPEED = 3;     // ENB on L298N - Enable pin (left motor)
const int ARDUINO_LEFT_MOTOR_DIR1 = 5;      // IN3 on L298N - Direction 1 (left motor)
const int ARDUINO_LEFT_MOTOR_DIR2 = 4;      // IN4 on L298N - Direction 2 (left motor)

// Arduino - SG90s connection pins
const int ARDUINO_UP_DOWN = 9;              // 1st SG90 (vertical eye movement)
const int ARDUINO_LEFT_RIGHT = A0;          // 2nd SG90 (horizontal eye movement)

// Angle limits (due to eye movement mechanism design) and center positions
const int DOWN_ANGLE = 50;                  // Lowest vertical position, i.e., look down (degrees)
const int UP_ANGLE = 110;                   // Highest vertical position, i.e., look up (degrees)
const int VERT_CENTER_ANGLE = 80;           // Vertical center position, i.e., look vertically forward (degrees)
const int LEFT_ANGLE = 120;                 // Leftmost position, i.e., look left (degrees)
const int RIGHT_ANGLE = 60;                 // Rightmost position, i.e., look right (degrees)
const int HORIZ_CENTER_ANGLE = 90;          // Horizontal center position, i.e., look horizontally forward (degrees)

// PWM speed values
const int MAX_SPEED = 255;                  // Max speed (100% duty cycle)
// below this value, this robot does not advance due to weight and friction!
const int MIN_USABLE_SPEED = 135;           // ~53% speed
const int REAL_STOP_SPEED = 0;              // Stopped (0% duty cycle)

// Durations (in milliseconds)
const int MOTORS_SHORT_DURATION = 500;
const int SERVOS_AND_DISPLAY_SHORT_DURATION = 400;
const int DISPLAY_LONG_DURATION = 3000;

// OLED display configuration
const int DISPLAY_WIDTH = 128;              // Display width in pixels
const int DISPLAY_HEIGHT = 64;              // Display height in pixels
const int OLED_RESET = -1;                  // Reset pin (shared with Arduino reset)

// Number of times to repeat each SG90s movement pattern (e.g., left to right)
const int NUM_ITERATIONS = 3;

// Servo objects
Servo up_down_servo;
Servo left_right_servo;

// OLED display object
Adafruit_SSD1306 display(DISPLAY_WIDTH, DISPLAY_HEIGHT, &Wire, OLED_RESET);

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
void advanceRobot(Direction direction, int speed, int duration) {
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
void turnRobot(Turn turnDirection, int speed, int duration) {
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
void stopRobot(int duration) {
    setMotorSpeed(ARDUINO_RIGHT_MOTOR_SPEED, REAL_STOP_SPEED);
    setMotorSpeed(ARDUINO_LEFT_MOTOR_SPEED, REAL_STOP_SPEED);
    delay(duration);
}

// #############################################################
// Helper 7: Initialize servos by attaching and centering them #
// #############################################################
void initializeServos() {
    // attach each Arduino pin (for a servo) to servo object
    up_down_servo.attach(ARDUINO_UP_DOWN);
    left_right_servo.attach(ARDUINO_LEFT_RIGHT);
 
    // center
    centerServos();
}

// ###################################################
// Helper 8: Move both servos to specified positions #
// ###################################################
void moveServos(int vertAngle, int horizAngle) {
    // since we move both servos we allow diagonal movement (e.g., down and left, up and right, etc.)
    up_down_servo.write(constrain(vertAngle, DOWN_ANGLE, UP_ANGLE));
    left_right_servo.write(constrain(horizAngle, RIGHT_ANGLE, LEFT_ANGLE));
    delay(SERVOS_AND_DISPLAY_SHORT_DURATION);
}

// ##############################################
// Helper 9: Center vertically and horizontally #
// ##############################################
void centerServos() {
    moveServos(VERT_CENTER_ANGLE, HORIZ_CENTER_ANGLE);
}

// #######################################################
// Helper 10: Test sequence one: left-right eye movement #
// #######################################################
void moveEyesLeftRight() {
    // move left to right while keeping the vertical center
    for (int i = 0; i < NUM_ITERATIONS; i++) {
        moveServos(VERT_CENTER_ANGLE, LEFT_ANGLE);
        updateDisplayWithCurrentServoPositions(VERT_CENTER_ANGLE, LEFT_ANGLE);
        moveServos(VERT_CENTER_ANGLE, RIGHT_ANGLE);
        updateDisplayWithCurrentServoPositions(VERT_CENTER_ANGLE, RIGHT_ANGLE);
    }
    // re-center
    centerServos();
    updateDisplayWithCurrentServoPositions(VERT_CENTER_ANGLE, HORIZ_CENTER_ANGLE);
}
 
// ####################################################
// Helper 11: Test sequence two: up-down eye movement #
// ####################################################
void moveEyesUpDown() {
    // move up to down while keeping the horizontal center
    for (int i = 0; i < NUM_ITERATIONS; i++) {
        moveServos(UP_ANGLE, HORIZ_CENTER_ANGLE);
        updateDisplayWithCurrentServoPositions(UP_ANGLE, HORIZ_CENTER_ANGLE);
        moveServos(DOWN_ANGLE, HORIZ_CENTER_ANGLE);
        updateDisplayWithCurrentServoPositions(DOWN_ANGLE, HORIZ_CENTER_ANGLE);
    }
    // re-center
    centerServos();
    updateDisplayWithCurrentServoPositions(VERT_CENTER_ANGLE, HORIZ_CENTER_ANGLE);
 }
 
// #######################################################################
// Helper 12: Test sequence three: top-left to bottom-right eye movement #
// #######################################################################
void moveEyesTopLeftToBottomRight() {
    for (int i = 0; i < NUM_ITERATIONS; i++) {
        moveServos(UP_ANGLE, LEFT_ANGLE);
        updateDisplayWithCurrentServoPositions(UP_ANGLE, LEFT_ANGLE);
        moveServos(DOWN_ANGLE, RIGHT_ANGLE);
        updateDisplayWithCurrentServoPositions(DOWN_ANGLE, RIGHT_ANGLE);
    }
    // re-center
    centerServos();
    updateDisplayWithCurrentServoPositions(VERT_CENTER_ANGLE, HORIZ_CENTER_ANGLE);
}

// ######################################################################
// Helper 13: Test sequence four: top-right to bottom-left eye movement #
// ######################################################################
void moveEyesTopRightToBottomLeft() {
    for (int i = 0; i < NUM_ITERATIONS; i++) {
        moveServos(UP_ANGLE, RIGHT_ANGLE);
        updateDisplayWithCurrentServoPositions(UP_ANGLE, RIGHT_ANGLE);
        moveServos(DOWN_ANGLE, LEFT_ANGLE);
        updateDisplayWithCurrentServoPositions(DOWN_ANGLE, LEFT_ANGLE);
    }
    // re-center
    centerServos();
    updateDisplayWithCurrentServoPositions(VERT_CENTER_ANGLE, HORIZ_CENTER_ANGLE);
}

// ###################################################
// Helper 14: Update OLED display with given message #
// ###################################################
void updateDisplayWithMessage(const String& message) {
    // clear display
    display.clearDisplay();
    // set font
    display.setFont(&FreeMono9pt7b);
    // set cursor
    display.setCursor(0,15);
    // print message from cursor position
    display.print(message);
    // update display
    display.display();
}

// #############################################################
// Helper 15: Update OLED display with current servo positions #
// #############################################################
void updateDisplayWithCurrentServoPositions(int upDownAngle, int leftRightAngle) {
    // clear display
    display.clearDisplay();
    // set font
    display.setFont(&FreeMono9pt7b);
    // set cursor for 1st print
    display.setCursor(0,15);
    // print left-right angle
    display.print("LR:" + String(leftRightAngle));
    // set cursor for 2nd print
    display.setCursor(0,30);
    // print up-down angle
    display.print("UD:" + String(upDownAngle));
    // update display
    display.display();
}

// ###########################################################
// Helper 16: Initialize OLED display and show Ready message #
// ###########################################################
void initializeDisplay() {
    // source: https://forum.arduino.cc/t/arduino-uno-ssd1306-allocation-failed-need-help-downsizing/1131175
    // initialize display with I2C address 0x3C
    if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
        // F() is an Arduino-specific macro that tells the compiler to keep that string literal in flash (program) memory instead of copying it into SRAM at runtime?
        Serial.println(F("SSD1306 allocation failed"));
        // Don't proceed (by looping forever) if display initialization fails
        for(;;);
    }
    // update display
    display.display();
    // give it time
    delay(DISPLAY_LONG_DURATION);
    
    // source: randomnerdtutorials.com/guide-for-oled-display-with-arduino/
    // clear display
    display.clearDisplay();
    // set text size to normal 1:1 pixel scale, color and cursor
    display.setTextSize(1);
    // draw white text
    display.setTextColor(SSD1306_WHITE);
    // start at (0,6) (x, y) offset
    display.setCursor(0,6);
    // use full 256 char 'Code Page 437' font
    display.cp437(true);

    // create 'Ready' message on display
    updateDisplayWithMessage("Ready");
    delay(SERVOS_AND_DISPLAY_SHORT_DURATION);
}

// ################################################################
// Helper 17: Parse and execute motor and servo movement commands #
// ################################################################
void processMotorAndServoCommands(const String& received_data) {
    // parse commands from "parameter1:value1,parameter2:value2,..."
    // leftMD: left motor direction
    // rightMD: right motor direction
    // motorsS: motor speed
    // angleVP: vertical position
    // angleHP: horizontal position
    String leftMD_str = "", rightMD_str = "";
    int motorsS = 0, angleVP = -1, angleHP = -1;

    // set start position at 0
    int start = 0;
    // and while received_data is not fully gone through
    while (start < received_data.length()) {
        // set end as the position of the 1st comma (starting from start)
        int end = received_data.indexOf(',', start);
        // and if no comma (i.e., indexOf returns -1), set end to end of received_data
        if (end == -1) end = received_data.length();
        
        // get the substring from start to end
        String part = received_data.substring(start, end);
        
        // extract command parameters
        if (part.startsWith("leftMD:"))         leftMD_str  = part.substring(7);
        else if (part.startsWith("rightMD:"))   rightMD_str = part.substring(8);
        else if (part.startsWith("motorsS:"))   motorsS     = part.substring(8).toInt();
        else if (part.startsWith("angleVP:"))   angleVP     = part.substring(8).toInt();
        else if (part.startsWith("angleHP:"))   angleHP     = part.substring(8).toInt();

        // and advance cursor
        start = end + 1;
    }

    // with all possible commands (leftMD, rightMD, motorsS,angleVP, angleHP):

    // execute L298N commands if present
    if (leftMD_str.length() && rightMD_str.length()) {
        if (leftMD_str == "10" && rightMD_str == "10") {
            advanceRobot(FORWARD, motorsS, MOTORS_SHORT_DURATION);
        }
        else if (leftMD_str == "01" && rightMD_str == "01") {
            advanceRobot(BACKWARD, motorsS, MOTORS_SHORT_DURATION);
        }
        else if (leftMD_str == "01" && rightMD_str == "10") {
            turnRobot(LEFT, motorsS, MOTORS_SHORT_DURATION);
        }
        else if (leftMD_str == "10" && rightMD_str == "01") {
            turnRobot(RIGHT, motorsS, MOTORS_SHORT_DURATION);
        }
        else {
            stopRobot(MOTORS_SHORT_DURATION);
        }
    }

    // execute SG90s commands if present
    if (angleVP != -1 && angleHP != -1) {
        moveServos(angleVP, angleHP);
    }
}

// ###############################################################
// Helper 18: Process serial commands received from ESP32-WROVER #
// ###############################################################
void processReceivedData(const String& received_data) {
    // incoming data can be:

    // WROVER network info to display (i.e., did it connect to the home WiFi or to the phone hotspot?)
    if (received_data.startsWith("SSID:")) {
        String ssid = received_data.substring(5);
        updateDisplayWithMessage(ssid);
    }

    // or SG90s and/or L298N movements
    else if (received_data.startsWith("leftMD:") || 
            received_data.startsWith("rightMD:") || 
            received_data.startsWith("motorsS:") || 
            received_data.startsWith("angleVP:") || 
            received_data.startsWith("angleHP:"))
    {
        processMotorAndServoCommands(received_data);
    }

    // or robot internal status
    else if (received_data.startsWith("Listening") || received_data.startsWith("Thinking")) {
        updateDisplayWithMessage(received_data);
    }
}

// ###############################################################################################
// Setup: Initialize L298N and SG90s pins, the display, and test servo sequence (runs only once) #
// ###############################################################################################
void setup() {
    // initialize serial communication setting the UART baud rate
    // UART: Universal Asynchronous Receiver/Transmitter
    Serial.begin(9600); // 9600 bauds or bits per second
    // initialize servos
    initializeServos();
    // initialize display
    initializeDisplay();
    // initialize motors
    initializeMotorsPins();

    // test
    moveEyesLeftRight();
    moveEyesUpDown();
    moveEyesTopLeftToBottomRight();
    moveEyesTopRightToBottomLeft();
}

// ##########################################################
// Loop: Continuously check for and process serial commands #
// ##########################################################
void loop() {
    // check for incoming serial characters (from the WROVER to Rx)
    if (Serial.available()) {
        // read data until newline (marking end of logs/commands)
        String received_data = Serial.readStringUntil('\n');
        // process all possible logs/commands
        processReceivedData(received_data);
    }
}