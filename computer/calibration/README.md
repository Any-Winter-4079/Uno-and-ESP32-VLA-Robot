# Notes on the `calibration/` code:

## Hardware Setup

- **Left Eye**: AI-Thinker ESP32-CAM
- **Right Eye**: M5Stack Wide ESP32-CAM
- **Camera Sensors**: OV2640 with fisheye lenses (using 7.5cm cables)

## Computer Setup

- Define in this line whether the robot and computer will share the phone hotspot (True) or the home WiFi (False) as the common network for communication:

```
USE_HOTSPOT = True
```

- Define in these lines the ESP32-CAMs' IPs the phone hotspot or home WiFi will assign (because you ask for them in the `esp32/cam/` sketches you flash to the ESP32-CAMs):

```
IP_LEFT = "172.20.10.11" if USE_HOTSPOT else "192.168.1.181"   # Left eye (AI-Thinker ESP32-CAM)
IP_RIGHT = "172.20.10.10" if USE_HOTSPOT else "192.168.1.180"  # Right eye (M5Stack Wide ESP32-CAM)
```

## ESP32 Setup

- Ensure both ESP32-CAMs are properly flashed with firmware that exposes the image endpoints
- Verify cameras are accessible at their respective IP addresses (e.g., open a couple of browser tabs and go to http://192.168.1.180:80/image.jpg and http://192.168.1.181:80/image.jpg) before running the script

## Capture Process

### Equipment Required

- Chessboard pattern (10x7 squares = 9x6 inner corners)
  - Can use: https://github.com/opencv/opencv/blob/4.x/doc/pattern.png
- Flat surface to mount the pattern

### Camera Alignment Check

Before capturing:

1. Open both ESP32-CAM IPs in browser to verify functionality
2. Use a fixed reference object (e.g., book spine) to check:
   - Cameras have similar rotation (spine angle matches in both views)
   - Cameras have similar height (spine position matches vertically)

### Capture Settings

Configurable parameters:

```
JPEG_QUALITY = [Set your value (I used 6)]
FRAME_SIZE = [Set your value (I used "FRAMESIZE_VGA")]
```

### Capture Instructions

1. Run the capture script
2. Hold the chessboard in various positions and angles
3. Ensure pattern is fully visible in both cameras
4. Press 's' to save the current image pair
5. Capture 14-40 good image pairs from different angles

## Calibration Process

### Preparation

Before running calibration:

- Measure the physical chessboard square size
- Update `SQUARE_SIZE` in the calibration script

### Calibration Steps

1. **Intrinsic Calibration** (per camera):

   - Camera matrix
   - Distortion coefficients
   - Rotation vectors
   - Translation vectors

2. **Extrinsic Calibration** (stereo pair):
   - Rotation matrix
   - Translation vector
   - Essential matrix
   - Fundamental matrix

### Best Practices

- Run calibration after every few captures to check quality
- Keep chessboard closer to the cameras for better results
- Don't over-tilt the chessboard
- Remove image pairs if corner detection fails
- 14-40 good image pairs typically sufficient

### Typical Error Values

Good calibration should achieve low error values. I got around (and if you can improve upon them, even better):

- Left Camera: ~0.29
- Right Camera: ~0.28
- Stereo Calibration: ~0.31

## Validation

After calibration:

1. Check reported RMS error values
2. Verify corner detection visually in saved side-by-side images
3. Test undistortion results using `undistortion_and_rectification/undistort_and_rectify.py`

## Notes and Troubleshooting

- Higher `JPEG_QUALITY` may help if you plan to stitch images for panoramic view
- Image size affects calibration quality and may need scaling if used with different resolution
- If corner detection fails or lines are incorrect, remove the problematic image pairs
- If insufficient good pairs remain, rerun `store_images_to_calibrate.py` to capture more
- Image synchronization between cameras is important for good calibration (if one lags over the other, i.e., takes significatly more time than the other to capture the image once instructed to, and you move the chessboard in between captures, they will get the pattern at different positions and it will not work well / at all)
