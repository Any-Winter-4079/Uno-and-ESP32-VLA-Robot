# Notes on the `computer/face_recognition/` code:

## Overview

This folder tests face recognition with DeepFace on images with known faces, known and no faces, and images from the 2x ESP32-CAM robot cameras, in the files:

- `benchmark_face_recognition_with_known_faces.py`, to test face detection (with one of 8 backends) and recognition (with one of 6 models) on faces (`1_test_images`) of people present in the database (`1_database`)
- `benchmark_face_recognition_with_known_and_no_faces.py`, to test face detection and recognition on faces (`2_test_images`) of people present in the database (`2_database`), in four views (front_close, front_far, side_close, side_far), and on no-face images (in which case there should be no recognition passing the threshold)
- `run_face_recognition.py`, to test face detection and recognition on frames from the 2x ESP32-CAM robot cameras

The scripts allow for the setting of one of the following backends (to detect faces):

```
DEEPFACE_BACKENDS = [
    "opencv",
    "ssd",
    "mtcnn",
    "retinaface",
    "mediapipe",
    "yolov8",
    "yunet",
    "fastmtcnn",
]
```

One of the following models (to match the detected face to its name):

```
DEEPFACE_MODELS = [
    "VGG-Face",
    "Facenet",
    "Facenet512",
    "OpenFace",
    "DeepID",
    "ArcFace"
]
```

And use one of the following distance metrics:

```
DISTANCE_METRICS = ["cosine", "euclidean", "euclidean_l2"]
```

## Computer Setup

- First, define in this line whether the robot and computer will share the phone hotspot (True) or the home WiFi (False) for communication:

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

- And in these lines, the timeout settings:

```
STREAM_TIMEOUT = 3               # seconds
CONFIG_TIMEOUT = 5               # seconds
```

## Dataset Creation

You can use any database you want, like [Labelled Faces in the Wild (LFW) Dataset](https://www.kaggle.com/datasets/jessicali9530/lfw-dataset?resource=download)

Personally, I took these steps:

### For Known Faces (for `benchmark_face_recognition_with_known_faces.py`)

- Take all people with names starting with 'A' (~432 people with ~1054 images)
- Move the last image of every person with 4+ images (up to 30 people) to a `1_test_images` folder
- Remove these test images from the `1_database` folder

The folders look as such:

```
1_database/
├── Aaron_Eckhart/
│   ├── Aaron_Eckhart_0001.jpg
├── Aaron_Guiel/
│   ├── Aaron_Guiel_0001.jpg
├── ...

1_test_images/
├── Aaron_Peirsol_0004.jpg
├── Abdoulaye_Wade_0004.jpg
├── ...
```

### For Known and No Faces (for `benchmark_face_recognition_with_known_and_no_faces.py`)

- Duplicate `1_database` to create the starting point for `2_database`
- Add specific known people (e.g., celebrities like Tom_Cruise, Salma_Hayek, Valentino_Rossi, and Arnold_Schwarzenegger)
- Include one or a few images per person in different poses (front_close, front_far, etc.)
- Create a `2_test_images` folder with:
  - 4 known people (in poses front_close, front_far, side_close, side_far)
  - 16 images without faces

The folders look as such:

```
2_database/
├── Aaron_Eckhart/
│   ├── Aaron_Eckhart_0001.jpg
├── Aaron_Guiel/
│   ├── Aaron_Guiel_0001.jpg
├── ...
├── Tom_Cruise/
│   ├── Tom_Cruise_0001.jpg
├── ...

2_test_images/
├── Salma_Hayek_front_close_known_0001.png
├── Salma_Hayek_front_far_known_0002.png
├── Salma_Hayek_side_close_known_0003.png
├── Salma_Hayek_side_far_known_0004.png
├── ...
├── unknown_0001.png
├── ...
```

### For the robot (for `run_face_recognition.py`)

- Create a `production_database` folder with images from people you want to recognize
- Include one or a few images per person
- If multiple, you can include different angles, such as front close, front far, side close, side far
- All production_database images are 512x512, although frames come at 640x480

The folder looks as such:

```
production_database/
├── Edu/
│   ├── Edu_0001.jpg
│   ├── ...
├── ...
```

## Notes

- Stereo rectification maps must exist in `../undistortion_and_rectification/stereo_maps/` because `run_face_recognition.py` calls `rectify_left_image`, and `rectify_right_image`
- `test_image_path` can be a numpy array in DeepFace. So we don't need to save the image to disk
