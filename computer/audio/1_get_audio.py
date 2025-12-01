import os
import io
import asyncio
import datetime
import websockets
from pydub import AudioSegment
from get_audio_and_run_speech_to_text_and_text_to_speech import allow_recording_when_robot_thinks_and_stays_quiet

#################
# Configuration #
#################

# Network configuration
USE_HOTSPOT = True                                                      # True for phone hotspot, False for home WiFi
WS_AUDIO_HOST = '172.20.10.4' if USE_HOTSPOT else "192.168.1.174"       # WebSocket server (computer) IP
WS_AUDIO_PORT = 8888                                                    # WebSocket server (computer) port
ESP32_WROVER_IP = "172.20.10.12" if USE_HOTSPOT else "192.168.1.182"    # ESP32-WROVER IP to send commands to

# Audio
SAMPLE_RATE = 16000                                                     # 16kHz required for Whisper compatibility
CHANNELS = 1                                                            # mono
BIT_DEPTH = 2                                                           # 16-bit audio (2 bytes per sample)
SAVE_FOLDER = "recorded_audio/"                                         # to save the resulting audio as .WAV after END_OF_AUDIO
END_OF_AUDIO_SIGNAL = "END_OF_AUDIO"                                    # ESP32-WROVER's special message to mark audio end

######################################
# Helper 1: WebSocket audio receiver #
######################################
async def audio_receiver(websocket):
    # create an in-memory buffer for incoming audio data
    audio_buffer = io.BytesIO()

    try:
        ###############################################################
        # For each WebSocket message received (from the ESP32-WROVER) #
        ###############################################################
        # NOTE: each message is either:
        # - raw PCM (Pulse-Code Modulation) bytes (PCM: standard form of digital audio in computers; https://en.wikipedia.org/wiki/Pulse-code_modulation)
        # - the text "END_OF_AUDIO"
        async for message in websocket:
            ##########################
            # If END_OF_AUDIO_SIGNAL #
            ##########################
            if message == END_OF_AUDIO_SIGNAL:
                ###################
                # Set cursor to 0 #
                ###################
                # cursor is reset to copy from the start since we longer want to append at the end
                audio_buffer.seek(0)

                ##########################################################
                # Convert the (full buffer) raw PCM data to AudioSegment #
                ##########################################################
                audio_segment = AudioSegment.from_raw(
                    audio_buffer,
                    sample_width=BIT_DEPTH,
                    frame_rate=SAMPLE_RATE,
                    channels=CHANNELS
                )

                ##############################
                # Export AudioSegment to WAV #
                ##############################
                wav_bytes = io.BytesIO()
                audio_segment.export(wav_bytes, format="wav")

                ##############
                # Save audio #
                ##############
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(SAVE_FOLDER, f"{timestamp}.wav")
                with open(filename, "wb") as wav_file:
                    wav_file.write(wav_bytes.getvalue())
                print(f"audio_receiver: audio saved to {filename}")

                ##########################
                # Set buffer to 0 length #
                ##########################
                audio_buffer.truncate(0)

                #####################################################
                # Allow (or reenable) recording on the ESP32-WROVER #
                #####################################################
                # NOTE: for a new run of this script not to fail due to the WROVER
                # being 'blocked' with allowRecording = false, we run:
                allow_recording_when_robot_thinks_and_stays_quiet(ESP32_WROVER_IP)

            ####################
            # If raw PCM bytes #
            ####################
            else:
                # copy message into the buffer and increment the internal pointer
                audio_buffer.write(message)

    except websockets.exceptions.ConnectionClosedError:
        print("audio_receiver: WebSocket connection closed unexpectedly.")
    
    except Exception as e:
        print(f"audio_receiver: error: {e}")
    
    finally:
        # free buffer
        audio_buffer.close()

#########################################
# Helper 2: WebSocket server entrypoint #
#########################################
# NOTE: start_audio_server is async because websockets.serve needs awaiting
async def start_audio_server():
    # start WS server on the computer listening on WS_AUDIO_HOST:WS_AUDIO_PORT
    # NOTE: websockets.serve returns a server object that stays alive as long as the event loop is running
    return await websockets.serve(audio_receiver, WS_AUDIO_HOST, WS_AUDIO_PORT)

########
# Test #
########
if __name__ == "__main__":
    # ensure the save folder exists
    os.makedirs(SAVE_FOLDER, exist_ok=True)

    # main is async because start_audio_server is async and needs awaiting
    async def main():
        # create and start the WebSocket server
        await start_audio_server()
        print("Audio WebSocket server started.")
        # keep main running indefinitely but let other coroutines -such as audio_receiver- run
        while True:
            await asyncio.sleep(1)

    # launch main which is async
    asyncio.run(main())
