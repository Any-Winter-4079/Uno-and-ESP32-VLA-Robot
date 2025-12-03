import os
import torch
from TTS.api import TTS

# tts --list_models | grep "/es"

#################
# Configuration #
#################

# Cloning and save paths
CLONING_VOICE_PATH = "cloning_voice/_tmp_gradio_ad73574f69f41643999d6e440c0df3da8e7ca067_output.wav"    # path to voice to clone
SAVE_PATH = "output.wav"                                                                                # path to save WAV file

# TTS models
# NOTE: mps either is not available, or looks on par or worse compared to cpu
DEVICE = "cpu"                                                                                          # cpu | cuda | mps?
TTS_MODELS = {
    "xtts_v2": {
        "path": "tts_models/multilingual/multi-dataset/xtts_v2",
        "voice_cloning": True,
        "language": "en"
    },
    "your_tts": {
        "path": "tts_models/multilingual/multi-dataset/your_tts",
        "voice_cloning": True,
        "language": "en"
    },
    "tortoise-v2": {
        "path": "tts_models/en/multi-dataset/tortoise-v2",
        "voice_cloning": False,
        "language": None
    },
    "speedy-speech": {
        "path": "tts_models/en/ljspeech/speedy-speech",
        "voice_cloning": True,
        "language": None
    },
    "vits": {
        "path": "tts_models/es/css10/vits",
        "voice_cloning": True,
        "language": None
    },
}
TTS_MODEL_KEY = "vits" # chosen TTS model

# Texts to convert to speech 
TEXTS = [
    "Yes, I am alive.",
    "Please use our dedicated channels for questions and discussion. Help is much more valuable if it's shared publicly so that more people can benefit from it.",
    "Pues he notado que recibo una lista de listas. Quisiera saber: primero, si están ordenadas según escribo las 'queries'; segundo, de dónde viene la otra lista que recibo; y tercero, si esta otra lista es en base a audio, visión, reconocimiento de cara, o qué"
]
TEXT_IDX = 2 # chosen text

#######################
# Results for xtts_v2 #
#######################
# ['Yes, I am alive.'] 1st time (cpu)
#  > Processing time: 4.986134052276611
#  > Real-time factor: 1.4124390525783568

# ['Yes, I am alive.'] 2nd time (cpu)
#  > Processing time: 5.095124006271362
#  > Real-time factor: 1.4245724834941613

# ['Please use our dedicated channels for questions and discussion.', "Help is much more valuable if it's shared publicly so that more people can benefit from it."] 1st time (cpu)
#  > Processing time: 20.508080005645752
#  > Real-time factor: 1.6115120172072386

# ['Please use our dedicated channels for questions and discussion.', "Help is much more valuable if it's shared publicly so that more people can benefit from it."] 2nd time (cpu)
#  > Processing time: 24.856979846954346
#  > Real-time factor: 1.54348136215121

# Output quality: Slow-paced, adds audio from another language at the end of sentences

########################
# Results for your_tts #
########################
# ['Yes, I am alive.'] 1st time (cpu)
#  > Processing time: 0.6283490657806396
#  > Real-time factor: 0.4131157565947664

# ['Yes, I am alive.'] 2nd time (cpu)
#  > Processing time: 0.5443038940429688
#  > Real-time factor: 0.3541339583883987

# ['Please use our dedicated channels for questions and discussion.', "Help is much more valuable if it's shared publicly so that more people can benefit from it."] 1st time (cpu)
#  > Processing time: 0.9728260040283203
#  > Real-time factor: 0.13507720133689535

# ['Please use our dedicated channels for questions and discussion.', "Help is much more valuable if it's shared publicly so that more people can benefit from it."] 2nd time (cpu)
#  > Processing time: 1.0387108325958252
#  > Real-time factor: 0.14454645596936058

# Output quality: Fast-paced, human with a slight robotic touch

###########################
# Results for tortoise-v2 #
###########################
# ['Yes, I am alive.'] 1st time (cpu)
#  > Processing time: 81.67530822753906
#  > Real-time factor: 26.146059036254883

# ['Yes, I am alive.'] 2nd time (cpu)
#  > Processing time: 83.08467197418213
#  > Real-time factor: 28.965611830108713

# ['Please use our dedicated channels for questions and discussion.', "Help is much more valuable if it's shared publicly so that more people can benefit from it."] 1st time (cpu)
#  > Processing time: 367.43839716911316
#  > Real-time factor: 31.51848880235803

# ['Please use our dedicated channels for questions and discussion.', "Help is much more valuable if it's shared publicly so that more people can benefit from it."] 2nd time (cpu)
#  > Processing time: 336.19041204452515
#  > Real-time factor: 30.5413587079012

# Output quality: Slow-paced, human, voice changes between sentences

#############################
# Results for speedy-speech #
#############################
# ['Yes, I am alive.'] 1st time (cpu)
#  > Processing time: 0.12953972816467285
#  > Real-time factor: 0.08200364624572337

# ['Yes, I am alive.'] 2nd time (cpu)
#  > Processing time: 0.1187138557434082
#  > Real-time factor: 0.07515045128451284

# ['Please use our dedicated channels for questions and discussion.', "Help is much more valuable if it's shared publicly so that more people can benefit from it."] 1st time (cpu)
#  > Processing time: 0.6444518566131592
#  > Real-time factor: 0.06299724889310611

# ['Please use our dedicated channels for questions and discussion.', "Help is much more valuable if it's shared publicly so that more people can benefit from it."] 2nd time (cpu)
#  > Processing time: 0.624000072479248
#  > Real-time factor: 0.06099802098776165

# Output quality: asian accent, fast-paced, somewhat robotic?

############
# Init TTS #
############
tts = TTS(TTS_MODELS[TTS_MODEL_KEY]["path"]).to(DEVICE)

###########
# Run TTS #
###########
tts.tts_to_file(
    text=TEXTS[TEXT_IDX],
    speaker_wav=CLONING_VOICE_PATH if TTS_MODELS[TTS_MODEL_KEY]["voice_cloning"] else None,
    language=TTS_MODELS[TTS_MODEL_KEY]["language"],
    file_path=SAVE_PATH
)