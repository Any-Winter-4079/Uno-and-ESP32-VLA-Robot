import sys
from os.path import dirname, join, abspath
sys.path.append(abspath(dirname(dirname(__file__))))

import cv2
import time
import numpy as np
from calibration.store_images_to_calibrate import update_camera_config
from depth.calculate_depth_with_depth_anything import get_stereo_images, rectify_left_image, rectify_right_image

#################
# Configuration #
#################

JPEG_QUALITY = 12                                                 # 0-63 (lower means higher quality)
FRAME_SIZE = "FRAMESIZE_VGA"                                      # 640x480 resolution
USE_HOTSPOT = True                                                # True for phone hotspot, False for home WiFi
RIGHT_EYE_IP = "172.20.10.10" if USE_HOTSPOT else "192.168.1.180" # ESP32-CAM right eye IP
LEFT_EYE_IP = "172.20.10.11" if USE_HOTSPOT else "192.168.1.181"  # ESP32-CAM left eye IP

STEREO_BLOCK_SIZE = 11                                            # matching block size (must be odd)
MIN_DISPARITY = 0                                                 # minimum disparity value
NUM_DISPARITIES = 5 * 16                                          # search range (must be divisible by 16)
SPECKLE_WINDOW_SIZE = 0                                           # speckle filter region size (0 means disabled)
SPECKLE_RANGE = 2                                                 # max disparity variation in speckle filtering
MODE = cv2.STEREO_SGBM_MODE_HH                                    # SGBM mode (HH means full-scale dynamic programming)
UNIQUENESS_RATIO = 0                                              # cost margin for uniqueness (0 means disabled)
PRE_FILTER_CAP = 0                                                # pre-filter intensity cap before matching
DISP12MAX_DIFF = 32                                               # max allowed disparity difference between left-right checks

# camera endpoints
esp32_right_image_url = f"http://{RIGHT_EYE_IP}/image.jpg"
esp32_left_image_url = f"http://{LEFT_EYE_IP}/image.jpg"
esp32_left_config_url = f"http://{LEFT_EYE_IP}/camera_config"
esp32_right_config_url = f"http://{RIGHT_EYE_IP}/camera_config"

# load stereo calibration maps
# NOTE: run computer/undistortion_and_rectification/undistort_and_rectify.py first
stereo_maps_dir = '../undistortion_and_rectification/stereo_maps'
Q = np.load(join(stereo_maps_dir, 'Q.npy'))                       # reprojection matrix (disparity -> 3D points)

# reference: https://learnopencv.com/depth-perception-using-stereo-camera-python-c/

# initialize SGBM stereo matching algorithm
sgbm_stereo_matching = cv2.StereoSGBM_create(
   minDisparity=MIN_DISPARITY,
   numDisparities=NUM_DISPARITIES,
   blockSize=STEREO_BLOCK_SIZE,
   P1=8 * STEREO_BLOCK_SIZE**2,
   P2=32 * STEREO_BLOCK_SIZE**2,
   disp12MaxDiff=DISP12MAX_DIFF,
   preFilterCap=PRE_FILTER_CAP,
   uniquenessRatio=UNIQUENESS_RATIO,
   speckleWindowSize=SPECKLE_WINDOW_SIZE,
   speckleRange=SPECKLE_RANGE,
   mode=MODE
)

###############################################################################
# Helpers 1-9: Trackbar callback functions for real-time parameter adjustment #
###############################################################################
def on_min_disparity_change(val):
   global sgbm_stereo_matching
   sgbm_stereo_matching.setMinDisparity(val)

def on_num_disparities_change(val):
   global sgbm_stereo_matching
   sgbm_stereo_matching.setNumDisparities(max(16, (val // 16) * 16))

def on_block_size_change(val):
   global sgbm_stereo_matching
   sgbm_stereo_matching.setBlockSize(val if val % 2 == 1 else val + 1)

def on_speckle_window_size_change(val):
   global sgbm_stereo_matching
   sgbm_stereo_matching.setSpeckleWindowSize(val)

def on_speckle_range_change(val):
   global sgbm_stereo_matching
   sgbm_stereo_matching.setSpeckleRange(val)

def on_mode_change(val):
   global sgbm_stereo_matching
   sgbm_stereo_matching.setMode(cv2.STEREO_SGBM_MODE_HH if val == 0 else cv2.STEREO_SGBM_MODE_SGBM_3WAY)

def on_uniqueness_ratio_change(val):
   global sgbm_stereo_matching
   sgbm_stereo_matching.setUniquenessRatio(val)

def on_pre_filter_cap_change(val):
   global sgbm_stereo_matching
   sgbm_stereo_matching.setPreFilterCap(val)

def on_disp12max_diff_change(val):
   global sgbm_stereo_matching
   sgbm_stereo_matching.setDisp12MaxDiff(val)

# create window and trackbars for parameter adjustment
cv2.namedWindow("SGBM disparity map")
cv2.createTrackbar("Min Disp.", "SGBM disparity map", MIN_DISPARITY, 32, on_min_disparity_change)
cv2.createTrackbar("Num Disp.", "SGBM disparity map", NUM_DISPARITIES, 16 * 10, on_num_disparities_change)
cv2.createTrackbar("Block Size", "SGBM disparity map", STEREO_BLOCK_SIZE, 13, on_block_size_change)
cv2.createTrackbar("Speckle Win", "SGBM disparity map", SPECKLE_WINDOW_SIZE, 200, on_speckle_window_size_change)
cv2.createTrackbar("Speckle Range", "SGBM disparity map", SPECKLE_RANGE, 100, on_speckle_range_change)
cv2.createTrackbar("Mode", "SGBM disparity map", 0, 1, on_mode_change)
cv2.createTrackbar("Uniq. Ratio", "SGBM disparity map", UNIQUENESS_RATIO, 60, on_uniqueness_ratio_change)
cv2.createTrackbar("Pre Filter Cap", "SGBM disparity map", PRE_FILTER_CAP, 100, on_pre_filter_cap_change)
cv2.createTrackbar("Disp12MaxDiff", "SGBM disparity map", DISP12MAX_DIFF, 60, on_disp12max_diff_change)

################################
# Helper 10: get face centroid #
################################
def get_face_centroid(face_detector, image):
   if not face_detector:
      return None
   # convert to RGB for MediaPipe
   rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
   # detect faces with MediaPipe
   results = face_detector.process(rgb_image)
   
   # if faces detected
   if results.detections:
       # use first detected face's bounding box
       detection = results.detections[0]
       # MediaPipe returns normalized coordinates in the range 0–1, relative to the full frame
       bboxC = detection.location_data.relative_bounding_box
       x, y, w, h = bboxC.xmin, bboxC.ymin, bboxC.width, bboxC.height
       # return the centroid
       return (x + w / 2, y + h / 2)
   return None

#######################################
# Helper 11: Calculate disparity maps #
#######################################
def calculate_disparity_maps(left_image_rectified, right_image_rectified):
   # convert to grayscale
   left_gray = cv2.cvtColor(left_image_rectified, cv2.COLOR_BGR2GRAY)
   right_gray = cv2.cvtColor(right_image_rectified, cv2.COLOR_BGR2GRAY)

   # compute disparity map
   disparity = sgbm_stereo_matching.compute(left_gray, right_gray) / 16.0

   # normalize for visualization
   norm_disparity = cv2.normalize(disparity, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)

   # calculate 3D coordinates
   points_3D = cv2.reprojectImageTo3D(disparity, Q)

   return norm_disparity, points_3D

#############################################################
# Main: calculate disparity map with SGBM on face detection #
#############################################################
# NOTE: this script was from initial testing, and isn't used later on; a few things to note:
# - Mediapipe's FaceDetection is explicitly initialized here for face detection, but later on, with DeepFace, if the
#   detection model is Mediapipe (you can set others), its internal code is abstracted away (so the functionality 
#   here is unused for the robot and kept only as early testing for the final DeepFace + YOLO + SGBM script)
# - Face centroids are only used here as a proxy for only running SGBM upon certain conditions (like face detection)
# - You could use them for real depth (e.g., of face centroids), like in calculate_depth_and_run_face_recognition.py, 
#   but that script use YOLO to get depth of COCO classes, which makes more sense than depth of only faces
def main():
   # import and initialize MediaPipe here to avoid importing mp / an initialized detector in files
   # importing variables or functions from calculate_disparity_map_on_face_detection_with_SGBM.py
   import mediapipe as mp

   ##############
   # Initialize #
   ##############
   # initialize MediaPipe face detector
   mp_face_detector = mp.solutions.face_detection
   face_detector = mp_face_detector.FaceDetection(min_detection_confidence=0.5)
   # initialize performance metrics
   total_face_time = 0
   total_disparity_map_time = 0
   face_detection_iterations = 0
   disparity_map_iterations = 0
   # initialize stream state
   stream_to_recover = False

   ################################################
   # Update each ESP32-CAM frame quality and size #
   ################################################
   update_camera_config(esp32_left_config_url, JPEG_QUALITY, FRAME_SIZE)
   update_camera_config(esp32_right_config_url, JPEG_QUALITY, FRAME_SIZE)

   while True:
      ####################################
      # Handle stream recovery if needed #
      ####################################
      if stream_to_recover:
         print("main: stream is being recovered")
         # if the cameras ever restart and that is the reason why we can't reach them, they will lose our camera
         # config, so send it again (hoping they come back to life)
         update_camera_config(esp32_left_config_url, JPEG_QUALITY, FRAME_SIZE)
         update_camera_config(esp32_right_config_url, JPEG_QUALITY, FRAME_SIZE)
         # for now, we assume they don't need recovery, and give them a chance, calling get_stereo_images;
         # if it fails, it'll be switched back to True and we will try to send the config once more
         stream_to_recover = False
         # give time to the cameras to recover/process update_camera_config
         cv2.waitKey(1000)
       
      ##################################
      # Fetch images from both cameras #
      ##################################
      left_eye_image, right_eye_image = get_stereo_images(esp32_left_image_url, esp32_right_image_url)

      #####################################################################
      # Rectify both (since we need both) images; else, mark for recovery #
      #####################################################################
      if left_eye_image is not None and right_eye_image is not None:
         left_eye_image_rectified = rectify_left_image(left_eye_image)
         right_eye_image_rectified = rectify_right_image(right_eye_image)
      else:
         print("main: failed to fetch any image within timeout. Starting recovery")
         stream_to_recover = True
         continue
      
      ###################################
      # Compute and time face detection #
      ###################################
      face_start_time = time.time()
      left_centroid = get_face_centroid(face_detector, left_eye_image_rectified)
      right_centroid = get_face_centroid(face_detector, right_eye_image_rectified)
      total_face_time += (time.time() - face_start_time)
      face_detection_iterations += 1

      ##################################################
      # Calculate SGBM disparity if faces are detected #
      ##################################################
      if left_centroid is not None and right_centroid is not None:
         disparity_start_time = time.time()
         norm_disparity, points_3D = calculate_disparity_maps(left_eye_image_rectified, right_eye_image_rectified)
         total_disparity_map_time += (time.time() - disparity_start_time)
         disparity_map_iterations += 1
      else:
         print("main: failed to find face centroids in image pair")
         continue
         
      ##############################
      # Display SGBM disparity map #
      ##############################
      cv2.imshow("SGBM disparity map", norm_disparity)
      if cv2.waitKey(50) & 0xFF == ord('q'):
            break

   ##############################
   # Report performance metrics #
   ##############################
   if face_detection_iterations > 0:
      average_face_time = total_face_time / face_detection_iterations
      print(f"main: average face centroid calculation time over {face_detection_iterations} iterations: {average_face_time:.3f} seconds")
   if disparity_map_iterations > 0:
      average_disparity_map_time = total_disparity_map_time / disparity_map_iterations
      print(f"main: average disparity map calculation time over {disparity_map_iterations} iterations: {average_disparity_map_time:.3f} seconds")

########
# Test #
########
if __name__ == "__main__":
   main()