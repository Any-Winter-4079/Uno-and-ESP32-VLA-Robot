# Notes on the `computer/undistortion_and_rectification/` code:

## Configuration

Run `calibration/store_images_to_calibrate.py` and `calibration/calibrate.py`, and then set both output paths:

```
IMAGES_SAVE_PATH = './images/undistorted_and_rectified_calibration_images' # for the calibration images, rectified
RECTIFICATION_MAPS_SAVE_PATH = './stereo_maps'                             # for the rectification maps
```

Images to rectify (by default from the calibration process) are expected at:

```
LEFT_EYE_IMAGES_DIR = '../calibration/images/left_eye'
RIGHT_EYE_IMAGES_DIR = '../calibration/images/right_eye'
```

Calibration parameters are expected at:

```
CAMERA_MARIX_LEFT = np.load('../calibration/parameters/camera_matrix_left_eye.npy')
DIST_COEFFS_LEFT = np.load('../calibration/parameters/distortion_coeffs_left_eye.npy')
CAMERA_MARIX_RIGHT = np.load('../calibration/parameters/camera_matrix_right_eye.npy')
DIST_COEFFS_RIGHT = np.load('../calibration/parameters/distortion_coeffs_right_eye.npy')
R = np.load('../calibration/parameters/rotation_matrix.npy')
T = np.load('../calibration/parameters/translation_vector.npy')
```
