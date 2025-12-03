from os.path import dirname, join, abspath
project_root = abspath(dirname(dirname(__file__)))

import io
import time
import torch
import asyncio
import requests
import websockets
import numpy as np
from TTS.api import TTS
from scipy.io import wavfile
from collections import deque
from pydub import AudioSegment
from scipy.signal import resample
from transformers.pipelines.audio_utils import ffmpeg_read
from transformers import WhisperProcessor, WhisperForConditionalGeneration

#################
# Configuration #
#################

# Network configuration
USE_HOTSPOT = True                                                                              # True for phone hotspot, False for home WiFi
WS_AUDIO_HOST = "172.20.10.4" if USE_HOTSPOT else "192.168.1.174"                               # WebSocket server (computer) IP
WS_AUDIO_PORT = 8888                                                                            # WebSocket server (computer) port
ESP32_WROVER_IP = "172.20.10.12" if USE_HOTSPOT else "192.168.1.182"                            # ESP32-WROVER IP to send commands to

# Computer - ESP32-WROVER communication
ESP32_WROVER_ALLOW_RECORDING_ENDPOINT = "allowRecordingWhenRobotThinksAndStaysQuiet"            # ESP32-WROVER endpoint to re-enable recording 
ESP32_WROVER_STOP_RECORDING_UPON_SAME_TRANSCRIPT_ENDPOINT = "stopRecordingUponSameTranscript"   # ESP32-WROVER endpoint to ask it to stop sending audio
END_OF_AUDIO_SIGNAL = "END_OF_AUDIO"                                                            # special message to mark audio end

# Audio
SAMPLE_RATE = 16000                                                                             # 16kHz required for Whisper compatibility
CHANNELS = 1                                                                                    # mono
BIT_DEPTH = 2                                                                                   # 16-bit audio (2 bytes per sample)
NO_AUDIO_MESSAGE = ""                                                                           # audio message when there is no audio captured

# STT
MAX_SAME_TRANSCRIPTS = 4                                                                        # repeated transcript threshold before sending stop message to ESP32-WROVER (i.e., if last n speech -> text conversions resulted in the same text, we are probably appending silence to the buffer, which is taken as 'the person has likely stopped speaking and is awaiting our answer', and we move on to calling the VLA without waiting for the full 30s)
CHECK_INTERVAL = 1                                                                              # frequency (in seconds) of audio buffer transcript re-checking (i.e., every s seconds, convert speech -> text, resulting in something like at 1s: 'Hello, how', at 2s: 'Hello, how are you?', at 3s: 'Hello, how are you?', at 4s: 'Hello, how are you?', at 5s: 'Hello, how are you?', tell WROVER to stop sending audio due to MAX_SAME_TRANSCRIPTS)
MIN_WORDS_THRESHOLD = 3                                                                         # ignore if less than this word count (likely, noise incorrectly transcribed as text, although it could be a short message, such as 'Okay'). In this case, speak to the robot >= MIN_WORDS_THRESHOLD
STT_MODEL = "whisper-tiny"                                                                      # Whisper model variant (e.g., tiny, small, medium, large-v2)
STT_LANGUAGE = "es"                                                                             # 'es' (Spanish) | 'en' (English)

# TTS
TTS_MODEL = {
    "path": "tts_models/es/css10/vits",
    "voice_cloning": True,
    "language": None
}                                                                                               # TTS model config
TTS_DEVICE = "cpu"                                                                              # cpu | cuda | mps?
TTS_RESPONSE_AUDIO_PATH = join(
    project_root,
    "audio",
    "response.wav"
)                                                                                               # path to save WAV file
TTS_CLONING_VOICE_PATH = join(
    project_root,
    "audio",
    "cloning_voice",
    "_tmp_gradio_ad73574f69f41643999d6e440c0df3da8e7ca067_output.wav"
)                                                                                               # path to voice to clone
PLAY_SAME_AUDIO_BACK = False                                                                    # (for testing) True to test audio playback using as text the transcript of what is spoken to the robot (i.e., what you say, he says)

# load STT model
processor = WhisperProcessor.from_pretrained("openai/" + STT_MODEL)
model = WhisperForConditionalGeneration.from_pretrained("openai/" + STT_MODEL)

# init TTS
tts = TTS(TTS_MODEL["path"]).to(TTS_DEVICE)

# keep latest MAX_SAME_TRANSCRIPTS to call ESP32_WROVER_STOP_RECORDING_UPON_SAME_TRANSCRIPT_ENDPOINT if they are all equal
latest_transcripts = deque(maxlen=MAX_SAME_TRANSCRIPTS)

# global audio state for LLM/production.py
is_audio_recording = False                                                                      # to check whether audio is being sent from the ESP32-WROVER to the computer (and if so, wait for it to finish before calling the VLA)
latest_transcript = None                                                                        # text (converted with STT) to be passed to the VLA within <audio></audio>
vla_run_flag = False                                                                            # to set whether the VLA is running and audio processing is on hold, or whether audio processing can be re-enabled
speech = None                                                                                   # speech text to be converted to audio with TTS and then spoken
speech_flag = None                                                                              # None (pending) | True (to speak) | False (to stay quiet), set by LLM/production.py to True or False and reset here to None

#############################
# Helper 1: get audio state #
#############################
# NOTE: this function is used by:
# - LLM/production.py's wait_for_start_of_audio_with_timeout to check if is_audio_recording within AUDIO_TIMEOUT (this way, if audio is being sent by the robot to the computer, it will delay the VLA call, else it will move on with vision only)
# - LLM/production.py's wait_for_audio_to_finish to check if audio sending from the robot to the computer has ended, to call the VLA
# - LLM/production.py's main to get the latest transcript after audio sending from the robot to the computer has ended
def get_audio_state():
    return is_audio_recording, latest_transcript

####################################################
# Helper 2: set VLA state as running / not running #
####################################################
# NOTE: this function is used by:
# - audio_receiver to set vla_run_flag to True and therefore make itself discard any future incoming audio message, until LLM/production.py's main signals the VLA has finished running (by setting it to False). This can happen if:
#   - computer receives END_OF_AUDIO
#   - computer realizes last MAX_SAME_TRANSCRIPTS are the same
# - LLM/production.py's main to tell audio_receiver it should stop discarding incoming audio messages because the robot has finished thinking / the VLA has finished running
def set_vla_run_flag(value):
    global vla_run_flag
    vla_run_flag = value

###################################
# Helper 3: get VLA running state #
###################################
# NOTE: this function is used by:
# - audio_receiver to check vla_run_flag and discard any future incoming audio message, until LLM/production.py's main signals the VLA has finished running (by setting it to False)
def get_vla_run_flag():
    return vla_run_flag

###################################
# Helper 4: set text to be spoken #
###################################
# NOTE: this function is used by:
# - LLM/production.py's main to set text to be spoken, e.g., after:
# <bodyControl>
# {"speak": "Hello", "eyes_vertical_position": 90}
# </bodyControl>
# ...
# speech_text = body_control.get("speak")
# if speech_text:
#     # set the speech text
#     set_speech(speech_text)
def set_speech(text):
    global speech
    speech = text

######################################################
# Helper 5: set whether something needs to be spoken #
######################################################
# NOTE: this function is used by:
# - LLM/production.py's main to set speech_flag to True if there is some text to convert to speech via TTS and then speak, or False if not
def set_speech_flag(value):
    global speech_flag
    speech_flag = value

######################################################
# Helper 6: get whether something needs to be spoken #
######################################################
# NOTE: this function is used by:
# - audio_receiver to wait for LLM/production.py's main decision to speak or not before closing and recreating the buffer, marking the end of one turn of (possible) input audio -> VLA -> (possible) output audio
def get_speech_flag():
    return speech_flag

##################################################################################################################################
# Helper 7: tell the WROVER to stop sending audio (because latest MAX_SAME_TRANSCRIPTS are the same and it's likely silence now) #
##################################################################################################################################
def send_stop_recording_upon_same_transcript(ip):
    esp32_stop_url = f"http://{ip}/{ESP32_WROVER_STOP_RECORDING_UPON_SAME_TRANSCRIPT_ENDPOINT}"
    print(f"send_stop_recording_upon_same_transcript: sending request to: {esp32_stop_url}")
    data = {"stop": "true"}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    try:
        response = requests.post(esp32_stop_url, data=data, headers=headers, timeout=5)
        return {"success": True, "message": response.text}
    except requests.RequestException as e:
        return {"success": False, "message": str(e)}

###################################################################################################################
# Helper 8: tell the WROVER it can start recording again because the VLA finished (despite deciding not to speak) #
###################################################################################################################
def allow_recording_when_robot_thinks_and_stays_quiet(ip):
    esp32_allow_url = f"http://{ip}/{ESP32_WROVER_ALLOW_RECORDING_ENDPOINT}"
    print(f"allow_recording_when_robot_thinks_and_stays_quiet: sending request to {esp32_allow_url}")
    data = {"allow": "true"}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    try:
        response = requests.post(esp32_allow_url, data=data, headers=headers, timeout=5)
        return {"success": True, "message": response.text}
    except requests.RequestException as e:
        return {"success": False, "message": str(e)}

#####################
# Helper 9: run STT #
#####################
def run_stt(audio_buffer):
    ###################
    # Set cursor to 0 #
    ###################
    # cursor is reset to copy from the start
    audio_buffer.seek(0)

    ##################################
    # Quick check before running STT #
    ##################################
    buffer_size = audio_buffer.getbuffer().nbytes
    if buffer_size == 0:
        # transcript, token_probs
        return "", []

    #############################################################
    # Convert the (current buffer) raw PCM data to AudioSegment #
    #############################################################
    # NOTE: AudioSegment.from_raw reads the entire buffer so it advances the file pointer to EOF,
    # making the pointer be correctly positioned in the event we need to append new audio;
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
    
    ###########
    # Run STT #
    ###########
    # decode (raw 16-bit PCM) WAV into float32 array for Whisper
    inputs = ffmpeg_read(wav_bytes.getvalue(), sampling_rate=SAMPLE_RATE)

    # prepare input features for Whisper, converting the float32 audio into a log-mel spectrogram
    input_features = processor(inputs, sampling_rate=SAMPLE_RATE, language=STT_LANGUAGE, return_tensors="pt").input_features
    
    # generate token predictions from audio log-mel spectrogram:
    # log-mel spectrogram -> 2 × Conv1D + GELU -> encoder ->
    # (step 1) decoder token 1 (with self-attention and cross-attention with the full encoder output)
    # (step 2) decoder token 2 (with self-attention and cross-attention with the full encoder output)
    # ...
    # (step n) decoder token n (with self-attention and cross-attention with the full encoder output)
    with torch.no_grad():
        predicted_ids = model.generate(
            input_features, 
            max_new_tokens=512, 
            return_dict_in_generate=True, 
            output_scores=True
        )

    # decode token IDs to text
    transcript = processor.batch_decode(predicted_ids.sequences, skip_special_tokens=True)[0]

    # extract token probabilities
    token_probs = []
    # NOTE: steps refer to decoder steps, as shown above
    for step_scores in predicted_ids.scores:
        step_probs = torch.nn.functional.softmax(step_scores[0], dim=-1)
        top_prob, top_token = step_probs.max(dim=-1)
        token = processor.decode([top_token.item()])
        token_probs.append((token, top_prob.item()))

    # display probabilities
    for token, prob in token_probs:
        print(f"\t{token}: {prob:.4f}")

    return transcript, token_probs

######################
# Helper 10: Run TTS #
######################
def run_tts(text):
    tts.tts_to_file(
        text=text,
        speaker_wav=TTS_CLONING_VOICE_PATH if TTS_MODEL["voice_cloning"] else None,
        language=TTS_MODEL["language"],
        file_path=TTS_RESPONSE_AUDIO_PATH
    )
    return TTS_RESPONSE_AUDIO_PATH

############################################################
# Helper 11: send speech through Websocket to ESP32-WROVER #
############################################################
async def speak(websocket, text):
    audio_path = run_tts(text)
    await send_audio_to_esp32(websocket, audio_path)

######################################
# Helper 12: process full transcript #
######################################
async def process_full_transcript(transcript, websocket, play_same_audio_back=False):
    num_words = len(transcript.split())
    if num_words < MIN_WORDS_THRESHOLD:
        print(f"process_full_transcript: audio ignored due to: {num_words} < {MIN_WORDS_THRESHOLD} words")
        return False

    print(f"process_full_transcript: transcript meets minimum word threshold: {transcript}")
    print("process_full_transcript: audio transcript:", transcript)

    if play_same_audio_back:
        await speak(websocket, transcript)

    return True

#########################################
# Helper 13: send audio to ESP32-WROVER #
#########################################
async def send_audio_to_esp32(websocket, audio_file_path):
    try:
        sample_rate, audio_data = wavfile.read(audio_file_path)

        # ensure format is 16-bit PCM
        if audio_data.dtype != np.int16:
            audio_data = (audio_data * 32767).astype(np.int16)

        if sample_rate != SAMPLE_RATE:
            print(f"send_audio_to_esp32: resampling from {sample_rate} Hz to {SAMPLE_RATE} Hz")
            num_samples = int(len(audio_data) * SAMPLE_RATE / sample_rate)
            audio_data = resample(audio_data, num_samples).astype(np.int16)

        audio_bytes = audio_data.tobytes()

        # send in chunks
        chunk_size = 32768
        for i in range(0, len(audio_bytes), chunk_size):
            await websocket.send(audio_bytes[i:i + chunk_size])

        await websocket.send(END_OF_AUDIO_SIGNAL)
        print("send_audio_to_esp32: audio sent successfully over WebSocket to ESP32-WROVER")
    
    except Exception as e:
        print(f"send_audio_to_esp32: error: {str(e)}")

#######################################
# Helper 14: WebSocket audio receiver #
#######################################
async def audio_receiver(websocket, play_same_audio_back=False):
    global latest_transcripts, is_audio_recording, latest_transcript, speech_flag

    # create an in-memory buffer for incoming audio data
    audio_buffer = io.BytesIO()
    # initialize last check time (although it should be overwritten once a message comes)
    last_equal_transcripts_check_time = time.time()
    # only process full transcript after END_OF_AUDIO_SIGNAL or MAX_SAME_TRANSCRIPTS consecutive identical transcripts
    is_final_transcript = False
    current_transcript = ""

    async def close_and_recreate_buffer():
        nonlocal audio_buffer
        audio_buffer.close()
        audio_buffer = io.BytesIO()

    try:
        ###############################################################
        # For each WebSocket message received (from the ESP32-WROVER) #
        ###############################################################
        # NOTE: each message is either:
        # - raw PCM (Pulse-Code Modulation) bytes (PCM: standard form of digital audio in computers; https://en.wikipedia.org/wiki/Pulse-code_modulation)
        # - the text "END_OF_AUDIO"
        async for message in websocket:
            
            #############################
            # Discard if VLA is running #
            #############################
            if get_vla_run_flag():
                continue

            ##########################
            # If END_OF_AUDIO_SIGNAL #
            ##########################
            if message == END_OF_AUDIO_SIGNAL:
                ###########
                # Run STT #
                ###########
                current_transcript, _ = run_stt(audio_buffer)

                #################################################
                # Set transcript as final to move on to the VLA #
                #################################################
                is_final_transcript = True

            ###########################
            # If we are mid-listening #
            ###########################
            else:
                ##################
                # Append message #
                ##################
                audio_buffer.write(message)

                ###################################################
                # Update times for next transcript equality check #
                ###################################################
                # get current time
                current_time = time.time()
                # set the last time we checked for transcript equality (last_equal_transcripts_check_time) to current_time once,
                # because last_equal_transcripts_check_time may come from the prior audio_buffer (prior turn of audio messages)
                last_equal_transcripts_check_time = current_time if not is_audio_recording else last_equal_transcripts_check_time
                
                ################################
                # Set state as recording audio #
                ################################
                # NOTE: this is for:
                # - LLM/production.py 
                # - audio_receiver to avoid always having current_time == last_equal_transcripts_check_time
                is_audio_recording = True

                ##########################################################################################
                # Re-check current transcript against the last MAX_SAME_TRANSCRIPTS every CHECK_INTERVAL #
                ##########################################################################################
                if current_time - last_equal_transcripts_check_time >= CHECK_INTERVAL:
                    ###########
                    # Run STT #
                    ###########
                    current_transcript, _ = run_stt(audio_buffer)

                    #############################
                    # Update latest transcripts #
                    #############################
                    latest_transcripts.append(current_transcript)
                    print(f"audio_receiver: current transcript: '{current_transcript}'")

                    ##################################################
                    # Update time for next transcript equality check #
                    ##################################################
                    last_equal_transcripts_check_time = current_time

                    #################################################################################################
                    # If MAX_SAME_TRANSCRIPTS consecutive identical transcripts, prepare to give control to the VLA #
                    #################################################################################################
                    if len(latest_transcripts) == MAX_SAME_TRANSCRIPTS and len(set(latest_transcripts)) == 1 \
                        and len(current_transcript.split()) >= MIN_WORDS_THRESHOLD:

                        #####################################################################
                        # Notify the WROVER so it stops sending audio through the WebSocket #
                        #####################################################################
                        print(f"audio_receiver: {MAX_SAME_TRANSCRIPTS} consecutive identical transcripts detected. Sending stop signal")
                        result = send_stop_recording_upon_same_transcript(ESP32_WROVER_IP)
                        if result["success"]:
                            print("audio_receiver: stop recording upon same transcript command successfully sent to ESP32-WROVER")
                        else:
                            print(f"audio_receiver: failed to send stop recording upon same transcript command to ESP32-WROVER: {result['message']}")
                        
                        #################################################
                        # Set transcript as final to move on to the VLA #
                        #################################################
                        is_final_transcript = True

            #######################################
            # Process transcript if final version #
            #######################################
            if is_final_transcript:
                #########################################################################################
                # Give control to VLA (and discard future WebSocket messages until control is returned) #
                #########################################################################################
                # after set_vla_run_flag(True), all new audio still sent (from WROVER to computer) 
                # until the WROVER processes the HTTP POST to /stopRecordingUponSameTranscript 
                # and stops sending further audio, will be immediately ignored by audio_receiver
                set_vla_run_flag(True)

                ###############################################################################
                # Ensure transcript validity (and play same transcript as audio if test mode) #
                ###############################################################################
                is_valid_transcript = await process_full_transcript(current_transcript, websocket, play_same_audio_back=play_same_audio_back)
                
                #####################################################################
                # Set state to no longer recording and set final transcript for VLA #
                #####################################################################
                is_audio_recording = False
                # set latest transcript for LLM/production.py
                latest_transcript = current_transcript if is_valid_transcript else NO_AUDIO_MESSAGE
                print(f"audio_receiver: final STT transcript: '{latest_transcript}'")

                ############################################
                # Determine whether the VLA wants to speak #
                ############################################
                # the VLA should be running here and we should wait for its decision on whether to speak or stay quiet.
                # In LLM/production.py, set_speech_flag(True | False) will be called at some point (after parsing bodyContro)l, which will contain whether to speak or not.
                #  Once we know (and do so if requested), we can start accepting incoming WebSocket messages, as well as let the WROVER know it can send audio again if any sound passes the KY-037's threshold
                print("audio_receiver: waiting for VLA's decision on whether to speak or stay quiet")
                while get_speech_flag() is None:
                    await asyncio.sleep(0.1)
                print("audio_receiver: detected VLA finished running due to speech flag being set")

                ###################################
                # Speak if the VLA wants to speak #
                ###################################
                if get_speech_flag():
                    print(f"audio_receiver: VLA has decided to speak: sending '{speech}' to ESP32-WROVER")
                    # if there is audio to speak, we await, because we don't want to record audio while we speak, anyway
                    await speak(websocket, speech)
                else:
                    print("audio_receiver: VLA has decided to stay quiet")
                
                #####################################################
                # Set speech flag to None (undecided) for next turn #
                #####################################################
                speech_flag = None

                ######################################################
                # Close and recreate buffer to prepare for next turn #
                ######################################################
                # new audio will be a new message/concept/idea, not to append to the existing buffer,
                # which contains audio the VLA has already responded/decided not to respond to, e.g.,
                await close_and_recreate_buffer()

                ###########################################################################
                # Reset transcripts and set final transcript state to False for next turn #
                ###########################################################################
                current_transcript = ""
                latest_transcripts.clear()
                is_final_transcript = False        

    except websockets.exceptions.ConnectionClosedError:
        print("audio_receiver: Websocket connection closed unexpectedly.")
    
    except Exception as e:
        print(f"audio_receiver: error: {e}")
    
    finally:
        # free buffer
        audio_buffer.close()
        # clear recent transcripts
        latest_transcripts.clear()

##########################################
# Helper 15: WebSocket server entrypoint #
##########################################
# NOTE: start_audio_server is async because websockets.serve needs awaiting
async def start_audio_server(play_same_audio_back=False):
    return await websockets.serve(
        lambda ws: audio_receiver(ws, play_same_audio_back=play_same_audio_back),
        WS_AUDIO_HOST,
        WS_AUDIO_PORT
    )

########
# Test #
########
if __name__ == "__main__":
    # main is async because start_audio_server is async and needs awaiting
    async def main():
        # create and start the WebSocket server
        await start_audio_server(play_same_audio_back=PLAY_SAME_AUDIO_BACK)
        print("Audio WebSocket server started.")
        # keep main running indefinitely but let other coroutines -such as audio_receiver- run
        while True:
            await asyncio.sleep(1)

    # launch main which is async
    asyncio.run(main())