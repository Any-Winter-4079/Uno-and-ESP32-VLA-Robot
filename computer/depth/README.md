# Notes on the `computer/depth/` code:

## Overview:

This folder tests two depth estimation methods, one relative and monocular (DepthAnything) and another absolute and binocular (SGBM), in the files:

- `calculate_depth_with_depth_anything.py`, to display depth maps on all frames
- `calculate_disparity_map_on_face_detection_with_SGBM.py`, to display disparity maps triggered by face recognition

Note while these are testing scripts, they build up functionality that eventually leads to `computer/depth_and_face_recognition/calculate_depth_and_run_face_recognition.py`, which combines DeepFace + YOLO (to detect objects which trigger depth estimation) + SGBM (to perform such depth estimation), and functions from both of these scripts are imported by the final vision script which runs `preprocess_frames`, itself imported by `LLM/production.py`.

## Computer Setup

- First, you will need to have run `computer/undistortion_and_rectification/undistort_and_rectify.py` to obtain the stereo rectification maps, which themselves require you to run `computer/calibration/store_images_to_calibrate.py` to obtain the calibration images and `computer/calibration/calibrate.py` to calibrate the cameras intrinsically and extrinsically.

- Then, define in this line whether the robot and computer will share the phone hotspot (True) or the home WiFi (False) for communication:

```
USE_HOTSPOT = True
```

- Define in these lines the 2x ESP32-CAM IPs:

```
RIGHT_EYE_IP = "172.20.10.10" if USE_HOTSPOT else "192.168.1.180"
LEFT_EYE_IP = "172.20.10.11" if USE_HOTSPOT else "192.168.1.181"
```

- Define in these lines the camera settings:

```
JPEG_QUALITY = 12                # 0-63 (lower means higher quality)
FRAME_SIZE = "FRAMESIZE_VGA"     # 640x480 resolution
```

- And in this line, the timeout setting:

```
STREAM_TIMEOUT = 3               # seconds
```

- Clone the [Depth Anything repository](https://github.com/LiheYoung/Depth-Anything) inside the `depth` folder (if you want to match this project, using commit `1d03336771fe09c5398ffdd211441e33941a97dc`)

- Then (if you use the same commit as this project) replace `run.py` and `dpt.py` with the updated files provided by this project's `depth_anything` folder, and rename the cloned repo `depth_anything`

- The structure should look like this:

```
depth
├── depth_anything
│   ├── depth_anything
│   │   ├── dpt.py (provided script)
│   │   ├── ... (cloned files)
│   └── run.py (provided script)
│   └── ... (cloned files)
├── calculate_depth_with_depth_anything.py
```

Finally, install DepthAnything's requirements before running `python calculate_depth_with_depth_anything.py`:

```
cd depth_anything
pip install -r requirements.txt
cd ..
```
