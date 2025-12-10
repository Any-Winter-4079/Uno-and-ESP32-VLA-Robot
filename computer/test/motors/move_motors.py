import requests

#################
# Configuration #
#################

# Network configuration
USE_HOTSPOT = True                                                      # True for phone hotspot, False for home WiFi
ESP32_WROVER_IP = "172.20.10.12" if USE_HOTSPOT else "192.168.1.182"    # ESP32-WROVER IP to send commands to
ESP32_REQUEST_TIMEOUT = 5                                               # seconds

# Motors speed and directions
MIN_SPEED = 0                                                           # to stop moving
MAX_SPEED = 255                                                         # for max speed
FORWARD = "10"                                                          # to forward-rotate
BACKWARD = "01"                                                         # to backward-rotate
STOP = "00"                                                             # to stop

####################################
# Helper 1: move motors on command #
####################################
def move_motors(
    left_motor_direction,
    right_motor_direction,
    motors_speed,
    esp32_wrover_ip=ESP32_WROVER_IP,
    timeout=ESP32_REQUEST_TIMEOUT
    ):
    esp32_wrover_command_url = f"http://{esp32_wrover_ip}/command"
    data = {"leftMD": left_motor_direction, "rightMD": right_motor_direction, "motorsS": motors_speed}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    try:
        response = requests.post(esp32_wrover_command_url, data=data, headers=headers, timeout=timeout)
        return {"success": True, "message": response.text}
    except requests.RequestException as e:
        return {"success": False, "message": str(e)}

############################
# Helper 2: get user input #
############################
def get_user_input():
    user_input = input(
        "Enter left motor direction, right motor direction, and motors speed separated by spaces\n"
        f"Directions (per motor): '{FORWARD}' (forward), '{BACKWARD}' (backward), '{STOP}' (stop)\n"
        f"Speed (for both): {MIN_SPEED}-{MAX_SPEED}\n"
        "Or enter 'exit' to quit: "
    )
    
    if user_input.lower() == "exit":
        raise SystemExit
        
    left_motor_direction, right_motor_direction, motors_speed = user_input.split()
    motors_speed = int(motors_speed)
    
    valid_directions = [FORWARD, BACKWARD, STOP]
    if not (left_motor_direction in valid_directions and right_motor_direction in valid_directions \
        and MIN_SPEED <= motors_speed <= MAX_SPEED):
        raise ValueError(
            f"directions must be '{FORWARD}' (forward), '{BACKWARD}' (backward), or '{STOP}' (stop), "
            f"and speed, in range {MIN_SPEED}-{MAX_SPEED}"
        )

    return left_motor_direction, right_motor_direction, motors_speed

################################
# Main: move motors on command #
################################
def main():
    while True:
        try:
            left_motor_direction, right_motor_direction, motors_speed = get_user_input()
            move_motors_result = move_motors(
                left_motor_direction,
                right_motor_direction,
                motors_speed
            )
            if move_motors_result["success"]:
                print(f"Response from ESP32: {move_motors_result['message']}")
            else:
                print(f"main: error sending request: {move_motors_result['message']}")
        except ValueError as e:
            print(f"main: invalid input: {str(e)}")
        except SystemExit:
            break

########
# Test #
########
if __name__ == "__main__":
    main()