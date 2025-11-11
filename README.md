## Demos

<div align="center">

| Production demo 1: run `production.py` script | Production demo 2: run `production.py` script |          Test demo 1 (audio): run `audio/3_get_audio` `_and_run_speech` `_to_text.py` script          |                           Test demo 2 (motors): run `move_motors.ino` sketch                           |                          Test demo 3 (servos): run `move_servos.ino` sketch                           |
| :-------------------------------------------: | :-------------------------------------------: | :---------------------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------------------------------: | :---------------------------------------------------------------------------------------------------: |
|                                               |                                               | <video src="https://github.com/user-attachments/assets/ac0bfaeb-4b39-4dc6-85b0-21153741062f"></video> | <video src="https://github.com/user-attachments/assets/d75e50bf-0305-4aec-9e65-48008144198f"></video/> | <video src="https://github.com/user-attachments/assets/2021902d-ad89-4211-b0d0-7f4c2e0c3f04"></video> |

</div>

NOTE:

- Test demos check if a component works with some pre-defined behavior (e.g., move motors forward for 2 seconds, backward for 2 seconds, turn left for 3 seconds, turn right for 3 seconds).

- Production demos use the full pipeline, and commands come from the fine-tuned vision-language(-action) model.

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

## QuickStart

- Buy the electronic components, build/buy the chassis and eyes, and connect the components.
- Flash `esp32/cam/*-production.ino` to the 2x ESP32-CAM, calibrate the cameras (check `/calibration` [README](computer/calibration/README.md) and [guide](guides/05_esp32_cam_calibration_distortion_correction_and_rectification.md)), and save the rectification maps (check `/undistortion_and_rectification` [README](computer/undistortion_and_rectification/README.md) and [guide](guides/05_esp32_cam_calibration_distortion_correction_and_rectification.md)). Make sure the computer and the 2x ESP32-CAM are connected to the same network and check images are available on a browser from the computer (making an HTTP GET request to the ESP32-CAM endpoint).
- Flash the `arduino/test/move_motors.ino` sketch to the Arduino Uno and make sure wheels can move.
- Flash the `arduino/test/move_servos.ino` sketch to the Arduino Uno and make sure eyes can move.
- Flash `esp32/wrover/production.ino` to the ESP32-WROVER and `arduino/production.ino` to the Arduino Uno and make sure wheels and eyes can move upon command from the computer (sent to the ESP32-WROVER and forwaded to the Arduino Uno).

## Connection QuickStart

NOTE: `/handleCommand` should read `/command`.

<div align="left">
    <img width=400" alt="Servos and cameras communication summary" src="./images/original/servos-and-cameras-communication-summary.png">
    <img width="500" alt="Motor communication summary" src="./images/original/motors-communication-summary.png">
    <img width="500" alt="Audio communication summary" src="./images/original/audio-communication-summary.png">
</div>

## What changes would I make to current language models?

The changes I would make to this robot (which is a proxy for a very early prototype of a system with physical and virtual output interfaces running 24/7), are:

First: Temporally align:

- vision input
- audio input
- internal thinking output
- body control output (let's call it, output to perform actions on **physical interfaces**)
- function calls output (let's call it, output to perform actions on **virtual interfaces**)

This way: vision and audio are updated periodically, and the model can stop its thinking or acting mid-way, depending on the new input captured from the world.

The reason is because variable token-length output is a problem. Systems should be periodically updated with world input, and we should not delay this for variable lengths due to the model still beeing thinking, calling a function, etc. You cannot delay feeding the new world state to the model because it is still rambling with internal thinking, or calling a funtion, but you should also **not** supress thinking altogether (and say generate body control commands directly, which would probably lead to worse performance).

Second: Although this is of lower importance, I would prefer `input` + `output` to `user` + `assistant`. A user can always be part of the input (e.g., as part of an audio, text, etc. input interface), but asynchronous users is much better, in my opinion, than user/assistant. At some point, humans will be a bottleneck, and models should seek to **autonomously** solve problems, not constantly defer to users. So, because users may come in with feedback at unspecified times, `user` input should be asynchronous to model execution (in other words, let model run 24/7, trying to achieve a goal, and let user come in asynchronously). And while it may not make sense for many to run models this way (for now), the change from `user` + `assistant` to `input` + `output` is harmless, and will better align with future use of these models (and robotic applications).

Third: Finally, having each weight tied to every task is probably not going to work. If you move a weight opposite to the gradient to improve performance in one task, you have **no idea** how that will affect performance on another task. That is (to me) conceptually wrong. So, either you sample from past knowledge to keep refreshing what you know (and try to move the weight to improve on one task, while not hurting much the others), which is possibly very expensive (although with what frequency existing knowledge would need to be refreshed is unknown to me), or you need to persist knowledge that does not degrade because you learn something else (e.g., you don't forget how to ride a bike even if for 5 years you have not touched a bike and have learnt tons of other things). While Mixture-of-Experts is, probably, closest to this at the time, I would prefer dynamically loading (or routing to) an unbounded number of experts, because if the model is initially taught to perform well (and route between) N tasks, it may not scale well if later on faced with the challenge of learning M >> N tasks.
