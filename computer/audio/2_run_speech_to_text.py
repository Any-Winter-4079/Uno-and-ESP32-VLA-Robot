import time
from transformers.pipelines.audio_utils import ffmpeg_read
from transformers import WhisperProcessor, WhisperForConditionalGeneration

#################
# Configuration #
#################

# STT
SHORT_AND_QUIET = True          # True to use short_and_quiet.wav, False for long_and_loud.wav
STT_MODEL = "whisper-large-v2"  # Whisper model variant (e.g., tiny, small, medium, large-v2)

###########
# Results #
###########

# short_and_quiet.wav
# whisper-tiny       ~0.45s
# whisper-small      ~1.12s
# whisper-medium     ~2.83s
# whisper-large-v2   ~6.01s

# long_and_loud.wav
# whisper-tiny       ~0.66s
# whisper-small      ~2.39s
# whisper-medium     ~6.18s
# whisper-large-v2   ~11.26s

# select audio path based on config
if SHORT_AND_QUIET:
    audio_path = "./voice_for_stt/short_and_quiet.wav"
else:
    audio_path = "./voice_for_stt/long_and_loud.wav"

# load STT model
processor = WhisperProcessor.from_pretrained("openai/" + STT_MODEL)
model = WhisperForConditionalGeneration.from_pretrained("openai/" + STT_MODEL)

# set sample rate
sampling_rate = processor.feature_extractor.sampling_rate
print(f"Sampling rate: {sampling_rate}")

# read audio file as bytes
with open(audio_path, "rb") as f:
    inputs = f.read()

# decode WAV bytes into float32 array for Whisper
inputs = ffmpeg_read(inputs, sampling_rate=sampling_rate)

# start STT timing
start_time = time.time()

# prepare input features for Whisper, converting the float32 audio into a log-mel spectrogram
input_features = processor(inputs, sampling_rate=sampling_rate, return_tensors="pt").input_features

# generate token predictions from audio log-mel spectrogram
predicted_ids = model.generate(input_features, max_new_tokens=256)

# decode token IDs to text
transcript = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

# end STT timing
end_time = time.time()
time_taken = end_time - start_time

# get approximate number of words
num_words = len(transcript.split())

print(f"Time taken for STT: {time_taken:.2f} seconds")
print(f"Number of words in transcription: {num_words}")
print("Audio transcription:", transcript)
