import sys
from os.path import dirname, join, abspath
sys.path.append(abspath(dirname(dirname(__file__))))

import cv2
import time
import threading
import numpy as np
import urllib.request
from depth.depth_anything.run import get_depth
from calibration.store_images_to_calibrate import update_camera_config

#################
# Configuration #
#################

JPEG_QUALITY = 12                                                   # 0-63 (lower means higher quality)
FRAME_SIZE = "FRAMESIZE_VGA"                                        # 640x480 resolution
USE_HOTSPOT = True                                                  # True for phone hotspot, False for home WiFi
RIGHT_EYE_IP = "172.20.10.10" if USE_HOTSPOT else "192.168.1.180"   # ESP32-CAM right eye IP
LEFT_EYE_IP = "172.20.10.11" if USE_HOTSPOT else "192.168.1.181"    # ESP32-CAM left eye IP
STREAM_TIMEOUT = 3                                                  # seconds
CONFIG_TIMEOUT = 5                                                  # seconds

# camera endpoints
ESP32_RIGHT_IMAGE_URL = f"http://{RIGHT_EYE_IP}/image.jpg"
ESP32_LEFT_IMAGE_URL = f"http://{LEFT_EYE_IP}/image.jpg"
ESP32_LEFT_CONFIG_URL = f"http://{LEFT_EYE_IP}/camera_config"
ESP32_RIGHT_CONFIG_URL = f"http://{RIGHT_EYE_IP}/camera_config"

# load stereo calibration maps
# NOTE: run computer/undistortion_and_rectification/undistort_and_rectify.py first
STEREO_MAPS_DIR = "../undistortion_and_rectification/stereo_maps"
STEREO_MAP_L_X = np.load(join(STEREO_MAPS_DIR, "stereoMapL_x.npy"))   # left-eye map for x-coordinate rectification
STEREO_MAP_L_Y = np.load(join(STEREO_MAPS_DIR, "stereoMapL_y.npy"))   # left-eye map for y-coordinate rectification
STEREO_MAP_R_X = np.load(join(STEREO_MAPS_DIR, "stereoMapR_x.npy"))   # right-eye map for x-coordinate rectification
STEREO_MAP_R_Y = np.load(join(STEREO_MAPS_DIR, "stereoMapR_y.npy"))   # right-eye map for y-coordinate rectification

######################################
# Helper 1: fetch image with timeout #
######################################
def fetch_image_with_timeout(url, queue, timeout=STREAM_TIMEOUT):
    try:
        response = urllib.request.urlopen(url, timeout=timeout)
        numpy_image = np.array(bytearray(response.read()), dtype=np.uint8)
        image = cv2.imdecode(numpy_image, cv2.IMREAD_COLOR)
        queue.append(image)
    except Exception as e:
        print(f"fetch_image_with_timeout: timeout or error fetching frame from {url}: {str(e)}")
        queue.append(None)

#############################################
# Helper 2: get both images using threading #
#############################################
def get_stereo_images(url_left, url_right):
    queue_left, queue_right = [], []

    # start parallel image capture threads
    thread_left = threading.Thread(target=fetch_image_with_timeout, args=(url_left, queue_left))
    thread_right = threading.Thread(target=fetch_image_with_timeout, args=(url_right, queue_right))
    
    # start threads
    thread_left.start()
    thread_right.start()
    
    # wait for both threads to finish
    thread_left.join()
    thread_right.join()

    # retrieve images from the queues
    left_eye_image = queue_left[0]
    right_eye_image = queue_right[0]

    return left_eye_image, right_eye_image

################################
# Helper 3: rectify left image #
################################
def rectify_left_image(image, stereo_map_L_x=STEREO_MAP_L_X, stereo_map_L_y=STEREO_MAP_L_Y):
    image_rectified = cv2.remap(image, stereo_map_L_x, stereo_map_L_y, cv2.INTER_LINEAR)
    return image_rectified

#################################
# Helper 4: rectify right image #
#################################
def rectify_right_image(image, stereo_map_R_x=STEREO_MAP_R_X, stereo_map_R_y=STEREO_MAP_R_Y):
    image_rectified = cv2.remap(image, stereo_map_R_x, stereo_map_R_y, cv2.INTER_LINEAR)
    return image_rectified

#############################################
# Main: calculate depth with Depth Anything #
#############################################
def main():
    ##############
    # Initialize #
    ##############
    # initialize performance metrics
    total_depth_time = 0
    depth_iterations = 0
    # initialize stream state
    stream_to_recover = False

    ################################################
    # Update each ESP32-CAM frame quality and size #
    ################################################
    update_camera_config(ESP32_LEFT_CONFIG_URL, JPEG_QUALITY, FRAME_SIZE, timeout=CONFIG_TIMEOUT)
    update_camera_config(ESP32_RIGHT_CONFIG_URL, JPEG_QUALITY, FRAME_SIZE, timeout=CONFIG_TIMEOUT)

    while True:
        ####################################
        # Handle stream recovery if needed #
        ####################################
        if stream_to_recover:
            print("main: stream is being recovered")
            # if the cameras ever restart and that is the reason why we can't reach them, they will lose our camera
            # config, so send it again (hoping they come back to life)
            update_camera_config(ESP32_LEFT_CONFIG_URL, JPEG_QUALITY, FRAME_SIZE, timeout=CONFIG_TIMEOUT)
            update_camera_config(ESP32_RIGHT_CONFIG_URL, JPEG_QUALITY, FRAME_SIZE, timeout=CONFIG_TIMEOUT)
            # for now, we asume they don't need recovery, and give them a chance, calling get_stereo_images;
            # if it fails, it'll be switched back to True and we will try to send the config once more
            stream_to_recover = False
            # give time to the cameras to recover/process update_camera_config
            cv2.waitKey(1000)
        
        ##################################
        # Fetch images from both cameras #
        ##################################
        left_eye_image, right_eye_image = get_stereo_images(ESP32_LEFT_IMAGE_URL, ESP32_RIGHT_IMAGE_URL)

        ######################################################################################
        # Rectify right image (preferrably), and if not, left image; else, mark for recovery #
        ######################################################################################
        if right_eye_image is not None:
            rectified_image = rectify_right_image(right_eye_image)
        elif left_eye_image is not None:
            rectified_image = rectify_left_image(left_eye_image)
        else:
            print("main: failed to fetch any image within timeout. Starting recovery")
            stream_to_recover = True
            continue

        ##############################
        # Compute and time depth map #
        ##############################
        depth_start_time = time.time()
        depth = get_depth(rectified_image)
        total_depth_time += (time.time() - depth_start_time)
        depth_iterations += 1
        
        #####################
        # Display depth map #
        #####################
        cv2.imshow("Depth Anything depth map", depth)
        if cv2.waitKey(50) & 0xFF == ord("q"):
            break
    
    ##############################
    # Report performance metrics #
    ##############################
    if depth_iterations > 0:
        average_depth_time = total_depth_time / depth_iterations
        print(f"main: average depth calculation time over {depth_iterations} iterations: {average_depth_time:.3f} seconds")

########
# Test #
########
if __name__ == "__main__":
    main()