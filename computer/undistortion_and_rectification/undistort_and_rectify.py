import sys
from os import makedirs
from os.path import dirname, join, abspath, basename
sys.path.append(abspath(dirname(dirname(__file__))))
import cv2
import glob
import numpy as np

# NOTE: prior to running this script, run:
#   - calibration/store_images_to_calibrate.py
#   - calibration/calibrate.py

#################
# Configuration #
#################

# Input paths (need the calibration images)
LEFT_EYE_IMAGES_DIR = '../calibration/images/left_eye'
RIGHT_EYE_IMAGES_DIR = '../calibration/images/right_eye'

# Storage paths
IMAGES_SAVE_PATH = './images/undistorted_and_rectified_calibration_images'
RECTIFICATION_MAPS_SAVE_PATH = './stereo_maps' # dir

# Calibration parameters (need the calibration parameters)
CAMERA_MARIX_LEFT = np.load('../calibration/parameters/camera_matrix_left_eye.npy')
DIST_COEFFS_LEFT = np.load('../calibration/parameters/distortion_coeffs_left_eye.npy')
CAMERA_MARIX_RIGHT = np.load('../calibration/parameters/camera_matrix_right_eye.npy')
DIST_COEFFS_RIGHT = np.load('../calibration/parameters/distortion_coeffs_right_eye.npy')
R = np.load('../calibration/parameters/rotation_matrix.npy')
T = np.load('../calibration/parameters/translation_vector.npy')

RECTIFICATION_FLAGS = cv2.CALIB_ZERO_DISPARITY # use zero disparity setting for better results with parallel cameras

#############################################
# Helper 1: Initialize stereo rectification #
#############################################
def initialize_stereo_rectification(image_size):
    # calculate rectification transforms
    # Q is the disparity-to-depth mapping matrix
    R1, R2, P1, P2, Q = cv2.fisheye.stereoRectify(
        CAMERA_MARIX_LEFT,
        DIST_COEFFS_LEFT,
        CAMERA_MARIX_RIGHT,
        DIST_COEFFS_RIGHT,
        image_size,
        R,
        T,
        flags=RECTIFICATION_FLAGS
    )
    
    # initialize undistortion and rectification maps for both cameras
    stereoMapL = cv2.fisheye.initUndistortRectifyMap(
        CAMERA_MARIX_LEFT,
        DIST_COEFFS_LEFT,
        R1,
        P1,
        image_size,
        cv2.CV_16SC2
    )
    stereoMapR = cv2.fisheye.initUndistortRectifyMap(
        CAMERA_MARIX_RIGHT,
        DIST_COEFFS_RIGHT,
        R2,
        P2,
        image_size,
        cv2.CV_16SC2
    )
    
    return stereoMapL, stereoMapR, Q

##############################
# Helper 2: Save stereo maps #
##############################
def save_stereo_maps(stereoMapL, stereoMapR, Q):
    # set up output dir
    makedirs(RECTIFICATION_MAPS_SAVE_PATH, exist_ok=True)
    
    # save individual map components for both cameras
    np.save(join(RECTIFICATION_MAPS_SAVE_PATH, 'stereoMapL_x.npy'), stereoMapL[0])
    np.save(join(RECTIFICATION_MAPS_SAVE_PATH, 'stereoMapL_y.npy'), stereoMapL[1])

    np.save(join(RECTIFICATION_MAPS_SAVE_PATH, 'stereoMapR_x.npy'), stereoMapR[0])
    np.save(join(RECTIFICATION_MAPS_SAVE_PATH, 'stereoMapR_y.npy'), stereoMapR[1])
    
    np.save(join(RECTIFICATION_MAPS_SAVE_PATH, 'Q.npy'), Q)

############################
# Helper 3: Process images #
############################
def process_images():
    # find and sort all input images
    left_images = sorted(glob.glob(join(LEFT_EYE_IMAGES_DIR, '*.jpg')))
    right_images = sorted(glob.glob(join(RIGHT_EYE_IMAGES_DIR, '*.jpg')))
    
    # set up output dir
    makedirs(IMAGES_SAVE_PATH, exist_ok=True)

    # get image size from first image (all images should be the same size)
    first_left_image = cv2.imread(left_images[0])
    image_size = first_left_image.shape[1], first_left_image.shape[0]
    
    # initialize rectification maps
    stereoMapL, stereoMapR, Q = initialize_stereo_rectification(image_size)

    # save maps for future use (avoids recomputation)
    #  - used in depth/calculate_depth_with_depth_anything.py (functions rectify_right_image, rectify_left_image)
    #  - which are imported by depth_and_face_recognition/calculate_depth_and_run_face_recognition.py (preprocess_frames)
    #  - which is imported by LLM/production.py (and called in main())
    save_stereo_maps(stereoMapL, stereoMapR, Q)

    # process each image pair
    for left_image_path, right_image_path in zip(left_images, right_images):
        # load images
        left_image = cv2.imread(left_image_path)
        right_image = cv2.imread(right_image_path)

        # apply undistortion and rectification
        left_image_rectified = cv2.remap(left_image, stereoMapL[0], stereoMapL[1], cv2.INTER_LINEAR)
        right_image_rectified = cv2.remap(right_image, stereoMapR[0], stereoMapR[1], cv2.INTER_LINEAR)

        # combine images side-by-side for visualization
        combined = np.concatenate((left_image_rectified, right_image_rectified), axis=1)
        
        # save the combined rectified image
        output_path = join(IMAGES_SAVE_PATH, basename(left_image_path))
        cv2.imwrite(output_path, combined)

        print(f"Processed and saved {left_image_path} and {right_image_path}")

###########################
# Main: Run rectification #
###########################
def main():
    process_images()
    print(f"Rectified images saved to {IMAGES_SAVE_PATH}")
    print(f"Stereo rectification maps saved to {RECTIFICATION_MAPS_SAVE_PATH}")

if __name__ == "__main__":
    main()