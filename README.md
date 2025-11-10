## How to Read this Project

- [Connections](guides/00_connections.md): Wiring (Fritzing) - how cables connect together
  - In general, we have: (i) 2x sources of power (and 2x converters, one from 7.4V down to 5V, another from 5V down to 3.3V), (ii) 2x ESP32-CAM and 2x OV2640 for sight movable by 2x SG-90, (iii) 1x L298N to control motors and 2x DC hobby motors, (iv) 1x KY-037 to detect sound and 1x INMP441 to record it, (v) 1x MAX98357A amplifier and 1x speaker to play audio, and (vi) 1x ESP32-WROVER (to communicate with the computer) and 1x Arduino Uno (to communicate with the L298N and 2x SG-90).
- [Components](guides/01_components.md): List of components (including devices and tools)
- [Chassis and motors](guides/02_chassis_and_motors.md): Instructions for chassis building and Arduino and L298N attachment
  - This includes cutting, sanding, drilling, and joining of the levels by hexagonal spacers, but feel free to buy a pre-made chassis or 3D print it.
  - Contains communication diagram between computer, ESP32-WROVER, Arduino Uno, L298N, and motors.
- [Vision and eye movement](guides/03_vision_and_eye_movement.md): Instructions for eye fabrication
  - This includes casting the eyes, inserting 1x OV2640 inside each eye, connecting it to 1x ESP32-CAM and creating the eye movement mechanism.
  - Contains communication diagram between computer, ESP32-WROVER, Arduino Uno and 2x SG90 for eye movement, and between computer and 2x ESP32-CAM for sight.
- [ESP32-CAM frame rate study](guides/04_esp32_cam_frame_rate_study.md): Quality/size fps study
  - This is a frame rate study which makes sense to be aware of if you take multiple images to feed a video to the robot (as you should; this project passes multiple still images to the vision-language model, but fine-tuning on a non-stop video roll dataset would be better).
- [ESP32-CAM calibration, distortion correction and rectification](guides/05_esp32_cam_calibration_distortion_correction_and_rectification.md): How to rectify distorted images
  - My OV2640 are fisheye, which distort the edges of images, so these scripts have the code to calibrate both cameras, and rectify the frames (before passing them to the vision-language model).
- [Audio capture and playback](guides/06_audio_capture_and_playback.md): How to handle thinking,
  - Contains communication diagram between KY-037, INMP441, ESP32-WROVER, and computer for audio capture, and computer, ESP32-WROVER, MAX98357A and speaker for audio playback.
  - The vision-language model does not take audio nor generate audio (directly). Whisper is used for Speech-to-Text and Coqui for Text-to-Speech, but feel free to add an end-to-end model (only thing is, make sure not all output is verbized, as there is internal thinking, body control and function call commands not meant to be spoken).

## Demos

<div align="center">

|   Production demo 1: run `production.py` to reproduce   |   Production demo 2: run `production.py` to reproduce   | Test demo 1 (audio): run `audio/3_get_audio_` `and_run_speech_` `to_text.py` to reproduce | Test demo 2 (motors): run `move_motors.ino` sketch to reproduce | Test demo 3 (servos): `run move_servos.ino` sketch to reproduce |
| :-----------------------------------------------------: | :-----------------------------------------------------: | :---------------------------------------------------------------------------------------: | :-------------------------------------------------------------: | :-------------------------------------------------------------: |
| <video src="videos/compressed/move_servos.mp4"></video> | <video src="videos/compressed/move_servos.mp4"></video> |              <video src="videos/compressed/listen_and_run_stt.mp4"></video>               |    <video src="videos/compressed/move_motors.mp4"></video/>     |     <video src="videos/compressed/move_servos.mp4"></video>     |

</div>
