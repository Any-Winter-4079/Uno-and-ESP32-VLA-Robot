import os
import re
import cv2
import glob
import numpy as np

#################
# Configuration #
#################

# 'chessboard' configuration
SQUARE_SIZE = 2.45                  # square size in centimeters
CHESSBOARD_SIZE = (9, 6)            # inner corner dimensions (width, height)
CORNER_SUBPIX_WINDOW_SIZE = (9, 9)  # corner refinement window size

# object points for chessboard corners in 3D space
objp = np.zeros((CHESSBOARD_SIZE[0]*CHESSBOARD_SIZE[1], 3), np.float32)
objp[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0], 0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2) * SQUARE_SIZE

# lists for calibration points
imgpoints_left = []                 # 2D points in left image plane
imgpoints_right = []                # 2D points in right image plane

def extract_timestamp(filename):
    # filename format: image_YYYYMMDD_HHMMSS.jpg
    match = re.search(r'(\d{8}_\d{6})', filename)
    return match.group(0) if match else None

def show_side_by_side(img1, img2, window_name='Side-by-side', display_time=500):
    # concatenate images side by side
    combined_image = np.concatenate((img1, img2), axis=1)
    # display and destroy
    cv2.imshow(window_name, combined_image)
    cv2.waitKey(display_time)
    cv2.destroyAllWindows()

def save_side_by_side(img1, img2, filename, output_dir):
    # concatenate images side by side
    combined_image = np.concatenate((img1, img2), axis=1)
    # write to file
    cv2.imwrite(os.path.join(output_dir, filename), combined_image)

def process_image_pairs():
    # load images
    images_left = glob.glob('images/left_eye/*.jpg')
    images_right = glob.glob('images/right_eye/*.jpg')

    # sort images by timestamp
    images_left.sort(key=extract_timestamp)
    images_right.sort(key=extract_timestamp)
    
    # ensure left and right counts match
    assert len(images_left) == len(images_right), "Different number of images for each camera"

    # set up output dir
    side_by_side_images_path = "images/corners_side_by_side"
    os.makedirs(side_by_side_images_path, exist_ok=True)

    # clear previous images
    for f in glob.glob(f"{side_by_side_images_path}/*"):
        os.remove(f)

    # set corner detection criteria
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    for img_left, img_right in zip(images_left, images_right):
        # ensure left and right timestamps match
        timestamp_left = extract_timestamp(img_left)
        timestamp_right = extract_timestamp(img_right)
        assert timestamp_left == timestamp_right, f"Timestamp mismatch: {img_left} and {img_right}"

        # read and convert images to grayscale
        imgL = cv2.imread(img_left)
        imgR = cv2.imread(img_right)
        grayL = cv2.cvtColor(imgL, cv2.COLOR_BGR2GRAY)
        grayR = cv2.cvtColor(imgR, cv2.COLOR_BGR2GRAY)

        # find chessboard corners
        retL, cornersL = cv2.findChessboardCorners(grayL, CHESSBOARD_SIZE, None)
        retR, cornersR = cv2.findChessboardCorners(grayR, CHESSBOARD_SIZE, None)

        if retL and retR:
            # refine corner positions
            cornersL = cv2.cornerSubPix(grayL, cornersL, CORNER_SUBPIX_WINDOW_SIZE, (-1, -1), criteria)
            cornersR = cv2.cornerSubPix(grayR, cornersR, CORNER_SUBPIX_WINDOW_SIZE, (-1, -1), criteria)

            # store calibration points
            imgpoints_left.append(cornersL)
            imgpoints_right.append(cornersR)

            # obtain, display, and store corners
            imgL_drawn = cv2.drawChessboardCorners(imgL.copy(), CHESSBOARD_SIZE, cornersL, retL)
            imgR_drawn = cv2.drawChessboardCorners(imgR.copy(), CHESSBOARD_SIZE, cornersR, retR)
            show_side_by_side(imgL_drawn, imgR_drawn, "Chessboard Corners")
            save_side_by_side(imgL_drawn, imgR_drawn, f"{timestamp_left}_side_by_side.jpg", side_by_side_images_path)
        else:
            print(f"Chessboard corners not found for {img_left} and {img_right}")

    # format data for calibration
    objpoints_reshaped = [objp.reshape(-1, 1, 3) for _ in range(len(imgpoints_left))]
    
    # ensure image points are in the correct format
    imgpoints_left_formatted = [ip.astype(np.float32) for ip in imgpoints_left]
    imgpoints_right_formatted = [ip.astype(np.float32) for ip in imgpoints_right]
    
    print("- object points shape and type:", np.array(objpoints_reshaped).shape, np.array(objpoints_reshaped).dtype)
    print("- image points left shape and type:", np.array(imgpoints_left_formatted).shape, np.array(imgpoints_left_formatted).dtype)
    print("- image points right shape and type:", np.array(imgpoints_right_formatted).shape, np.array(imgpoints_right_formatted).dtype)

    return grayL.shape[::-1], objpoints_reshaped, imgpoints_left_formatted, imgpoints_right_formatted

def calibrate_cameras(img_size, objpoints, imgpoints_left, imgpoints_right):
    # img_size: (width, height)
    # objpoints: 3D calibration points
    # imgpoints_left: 2D left camera points
    # imgpoints_right: 2D right camera points

    # prepare calibration arrays
    K_left = np.zeros((3, 3))   # left camera intrinsic matrix (contains the focal length and optical center)
    D_left = np.zeros((4, 1))   # left camera distortion coefficients (k1, k2, k3, k4 for fisheye)
    K_right = np.zeros((3, 3))  # right camera intrinsic matrix
    D_right = np.zeros((4, 1))  # right camera distortion coefficients

    # set calibration flags and criteria
    flags = cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC | cv2.fisheye.CALIB_CHECK_COND | cv2.fisheye.CALIB_FIX_SKEW
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6)

    calibration = {}

    # calibrate left camera
    try:
        rms_left, K_left, D_left, rvecs_left, tvecs_left = cv2.fisheye.calibrate(
            objpoints,
            imgpoints_left,
            img_size,
            K_left,
            D_left,
            flags=flags,
            criteria=criteria
        )
        print(f"Left camera calibration RMS error: {rms_left}")
        calibration.update(
            {
                'K_left': K_left,
                'D_left': D_left,
                'rvecs_left': rvecs_left,
                'tvecs_left': tvecs_left
            }
        )
    except Exception as e:
        print("Left camera calibration failed:", e)
        return None

    # calibrate right camera
    try:
        rms_right, K_right, D_right, rvecs_right, tvecs_right = cv2.fisheye.calibrate(
            objpoints,
            imgpoints_right,
            img_size,
            K_right,
            D_right,
            flags=flags,
            criteria=criteria
        )
        print(f"Right camera calibration RMS error: {rms_right}")
        calibration.update(
            {
                'K_right': K_right,
                'D_right': D_right,
                'rvecs_right': rvecs_right,
                'tvecs_right': tvecs_right
            }
        )
    except Exception as e:
        print("Right camera calibration failed:", e)
        return None

    # perform stereo calibration
    try:
        # R is the Rotation matrix (from camera 1's coordinate system to camera 2's)
        # T is the Translation vector (describes the position of camera 2 relative to camera 1)
        # E is the Essential matrix (encodes epipolar geometry between *calibrated* cameras)
        # F is the Fundamental matrix (encodes epipolar geometry between *uncalibrated* cameras, relating pixel coordinates)
        rms_stereo, _, _, _, _, R, T, E, F = cv2.fisheye.stereoCalibrate(
            objpoints,
            imgpoints_left,
            imgpoints_right,
            K_left,
            D_left,
            K_right,
            D_right,
            img_size,
            flags=cv2.fisheye.CALIB_FIX_INTRINSIC, # fix K and D matrices, only solve for R, T, E, F
            criteria=criteria
        )
        print(f"Stereo calibration RMS error: {rms_stereo}")
        calibration.update({'R': R, 'T': T, 'E': E, 'F': F})
    except Exception as e:
        print("Stereo calibration failed:", e)
        return None

    print("Camera matrix left eye:\n", K_left)
    print("Camera matrix right eye:\n", K_right)

    return calibration

def save_calibration_parameters(calibration):
    # set up output dir
    os.makedirs('parameters', exist_ok=True)
    
    # save intrinsic (per camera) calibration parameters
    for eye in ['left', 'right']:
        np.save(f'parameters/camera_matrix_{eye}_eye.npy', calibration[f'K_{eye}'])
        np.save(f'parameters/distortion_coeffs_{eye}_eye.npy', calibration[f'D_{eye}'])
        np.save(f'parameters/rotation_vec_{eye}_eye.npy', calibration[f'rvecs_{eye}'])
        np.save(f'parameters/translation_vec_{eye}_eye.npy', calibration[f'tvecs_{eye}'])
    
    # save stereo (across cameras) calibration parameters
    np.save('parameters/rotation_matrix.npy', calibration['R'])
    np.save('parameters/translation_vector.npy', calibration['T'])
    np.save('parameters/essential_matrix.npy', calibration['E'])
    np.save('parameters/fundamental_matrix.npy', calibration['F'])

def main():
    # process image pairs
    img_size, objpoints, imgpoints_left, imgpoints_right = process_image_pairs()
    
    # calibrate
    calibration = calibrate_cameras(img_size, objpoints, imgpoints_left, imgpoints_right)
    if calibration is None:
        print("Calibration failed")
        return
    
    # save calibration parameters
    save_calibration_parameters(calibration)
    print("Calibration succeeded (check output dir)")

if __name__ == "__main__":
    main()