import cv2
import requests
import threading
import numpy as np
import urllib.request
from os import makedirs
from os.path import join
from datetime import datetime

#################
# Configuration #
#################

# Network configuration
USE_HOTSPOT = True                                              # True for phone hotspot, False for home WiFi
IP_LEFT = "172.20.10.11" if USE_HOTSPOT else "192.168.1.181"    # left eye (AI-Thinker ESP32-CAM) IP
IP_RIGHT = "172.20.10.10" if USE_HOTSPOT else "192.168.1.180"   # right eye (M5Stack Wide ESP32-CAM) IP

# Camera settings
JPEG_QUALITY = 6                                                # 0-63, lower means higher quality
FRAME_SIZE = "FRAMESIZE_VGA"                                    # 640x480
CONFIG_TIMEOUT = 5                                              # seconds

# Image endpoints
ESP32_RIGHT_IMAGE_URL = f"http://{IP_RIGHT}/image.jpg"          # for GET
ESP32_LEFT_IMAGE_URL = f"http://{IP_LEFT}/image.jpg"            # for GET
# Config endpoints
ESP32_LEFT_CONFIG_URL = f"http://{IP_LEFT}/camera_config"       # for POST
ESP32_RIGHT_CONFIG_URL = f"http://{IP_RIGHT}/camera_config"     # for POST

# Storage paths
SAVE_PATH_RIGHT = "./images/right_eye"
SAVE_PATH_LEFT = "./images/left_eye"

# Capture parameters
MAX_CAPTURES = 100                  # at most, capture these many pairs (then choose whether to store each or not)
SECONDS_BETWEEN_IMAGE_CAPTURES = 3  # time to press 's' (before a new pair of frames is requested)

def update_camera_config(esp32_config_url, jpeg_quality, frame_size):
    data = {'jpeg_quality': jpeg_quality, 'frame_size': frame_size}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = requests.post(esp32_config_url, data=data, headers=headers, timeout=CONFIG_TIMEOUT)
        print(f"Response from ESP32-CAM: {response.text}")
        return True
    except Exception as e:
        print(f"Error sending update camera config request to ESP32-CAM: {e}")
        return False

def fetch_image(url, queue):
    try:
        response = urllib.request.urlopen(url)
        image_numpy = np.array(bytearray(response.read()), dtype=np.uint8)
        image = cv2.imdecode(image_numpy, cv2.IMREAD_COLOR)
        queue.append(image)
    except Exception as e:
        print(f"Error fetching frame from ESP32-CAM at {url}: {e}")
        queue.append(None)

def capture_stereo_images(url_left, url_right, save_path_left, save_path_right):
    queue_left, queue_right = [], []

    # start threads for parallel image capture
    thread_left = threading.Thread(target=fetch_image, args=(url_left, queue_left))
    thread_right = threading.Thread(target=fetch_image, args=(url_right, queue_right))
    
    thread_left.start()
    thread_right.start()

    # wait for both threads to complete
    thread_left.join()
    thread_right.join()

    # retrieve images from the queues
    image_left, image_right = queue_left[0], queue_right[0]

    # display preview of both images side-by-side
    if image_left is not None and image_right is not None:
        combined_image = cv2.hconcat([image_right, image_left])
        cv2.imshow("Pair preview (press 's' to store)", combined_image)
    else:
        print("Error: failed to retrieve one or both camera images")
    
    key = cv2.waitKey(SECONDS_BETWEEN_IMAGE_CAPTURES * 1000)

    # save images upon 's' key press
    if key == ord('s'):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_filename_left = join(save_path_left, f"image_{timestamp}.jpg")
        save_filename_right = join(save_path_right, f"image_{timestamp}.jpg")
        cv2.imwrite(save_filename_left, image_left)
        cv2.imwrite(save_filename_right, image_right)
        print(f"Saved {save_filename_left} and {save_filename_right}")
        return True
    return False

def main():
    # set up output dirs
    makedirs(SAVE_PATH_LEFT, exist_ok=True)
    makedirs(SAVE_PATH_RIGHT, exist_ok=True)

    # update camera configs (hitting each eye's endpoint with a POST request) with given JPEG_QUALITY and FRAME_SIZE
    update_camera_config(ESP32_LEFT_CONFIG_URL, JPEG_QUALITY, FRAME_SIZE)
    update_camera_config(ESP32_RIGHT_CONFIG_URL, JPEG_QUALITY, FRAME_SIZE)

    print("Instructions:")
    print("1. hold the printed 'chessboard' pattern in front of both cameras (so that both can capture it)")
    print("2. press 's' to save the current image pair")
    print("3. move the chessboard to a different position/angle")
    print("4. continue until you have sufficient images (I used 14, but take more pairs as many will be discarded)")
    print("\nStarting...\n\n")

    # start
    saved_count = 0
    for i in range(MAX_CAPTURES):
        print(f"Pair {i+1}/{MAX_CAPTURES}: please, position your chessboard and wait for the pair preview...")
        saved = capture_stereo_images(ESP32_LEFT_IMAGE_URL, ESP32_RIGHT_IMAGE_URL, 
                                     SAVE_PATH_LEFT, SAVE_PATH_RIGHT)
        if saved:
            saved_count += 1
            print(f"Pair {i+1} saved (total save count: {saved_count}). Capturing next pair")
        else:
            print(f"Pair {i+1} not saved. Capturing next pair")

    cv2.destroyAllWindows()
    print(f"\nStore images to calibrate completed. Total save count: {saved_count}")

if __name__ == "__main__":
    main()