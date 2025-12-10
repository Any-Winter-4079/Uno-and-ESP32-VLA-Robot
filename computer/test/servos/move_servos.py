import requests

#################
# Configuration #
#################

# Network configuration
USE_HOTSPOT = True                                                      # True for phone hotspot, False for home WiFi
ESP32_WROVER_IP = "172.20.10.12" if USE_HOTSPOT else "192.168.1.182"    # ESP32-WROVER IP to send commands to
ESP32_REQUEST_TIMEOUT = 5                                               # seconds

# Servo angle constraints (degrees)
DOWN_ANGLE = 50                                                         # lowest vertical position 
UP_ANGLE = 110                                                          # highest vertical position
LEFT_ANGLE = 120                                                        # leftmost horizontal position
RIGHT_ANGLE = 60                                                        # rightmost horizontal position

####################################
# Helper 1: move servos on command #
####################################
def move_servos(
    servo1_vertical_position,
    servo2_horizontal_position,
    esp32_wrover_ip=ESP32_WROVER_IP,
    timeout=ESP32_REQUEST_TIMEOUT
    ):
    esp32_wrover_command_url = f"http://{esp32_wrover_ip}/command"
    data = {"angleVP": servo1_vertical_position, "angleHP": servo2_horizontal_position}
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
    user_input = input(f"Enter vertical ({DOWN_ANGLE}-{UP_ANGLE}) and horizontal ({RIGHT_ANGLE}-{LEFT_ANGLE}) servo angles separated by a space, or 'exit' to quit: ")
    
    if user_input.lower() == "exit":
        raise SystemExit
        
    servo1_vertical_position, servo2_horizontal_position = map(int, user_input.split())
    
    if not (DOWN_ANGLE <= servo1_vertical_position <= UP_ANGLE and RIGHT_ANGLE <= servo2_horizontal_position <= LEFT_ANGLE):
        raise ValueError(f"the eyes's vertical angle must be in range {DOWN_ANGLE}-{UP_ANGLE}, and the horizontal angle, in range {RIGHT_ANGLE}-{LEFT_ANGLE}")
    
    return servo1_vertical_position, servo2_horizontal_position

################################
# Main: move servos on command #
################################
def main():
    while True:
        try:
            servo1_vertical_position, servo2_horizontal_position = get_user_input()
            move_servos_result = move_servos(
                servo1_vertical_position,
                servo2_horizontal_position
            )
            if move_servos_result["success"]:
                print(f"main: response from ESP32-WROVER: {move_servos_result['message']}")
            else:
                print(f"main: error sending request: {move_servos_result['message']}")
        except ValueError as e:
            print(f"main: invalid input: {str(e)}")
        except SystemExit:
            break

########
# Test #
########
if __name__ == "__main__":
    main()