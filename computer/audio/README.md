# Notes on the `computer/audio/` code:

## Overview

This folder incrementally builds the computer audio functionality, with:

- `1_get_audio.py`, to get audio sent by the ESP32-WROVER via Websocket
- `2_run_speech_to_text.py`, to run STT using Whisper on a local WAV file (and test several Whisper models)
- `3_get_audio_and_run_speech_to_text.py`, to combine the previous two scripts, getting audio from the WROVER and converting it into its transcription.
- `4_run_text_to_speech_coqui.py`, to run TTS using Coqui (and test various TTS models)
- `get_audio_and_run_speech_to_text_and_text_to_speech.py`, to put everything together (note this is the file that `LLM/production.py` imports; the rest are test files)

## Computer Setup

- Create `voice_for_stt/` and add a few test files, e.g., `short_and_quiet.wav` and `long_and_loud.wav`

- Create `cloning_voice/` and add one or a few voices to clone

- Define in this line whether the robot and computer will share the phone hotspot (True) or the home WiFi (False):

```
USE_HOTSPOT = True
```

- Define in this line the computer's IP:

```
WS_AUDIO_HOST = '172.20.10.4' if USE_HOTSPOT else '192.168.1.174'
```

- Define in this line the WROVER's IP:

```
ESP32_WROVER_IP = '172.20.10.12' if USE_HOTSPOT else '192.168.1.182'
```

## ESP32 Setup

- Make sure `esp32/wrover/production.ino` has been flashed to the ESP32-WROVER.

## Final Notes

- Make sure `ffmpeg` is installed (and on the system path) for `ffmpeg_read` to work.
- On Mac, enable MPS fallback:

```
export PYTORCH_ENABLE_MPS_FALLBACK=1
```
