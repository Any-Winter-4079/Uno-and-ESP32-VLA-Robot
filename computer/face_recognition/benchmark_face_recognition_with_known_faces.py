import sys
from os import listdir
from os.path import dirname, join, isfile, abspath
sys.path.append(abspath(dirname(dirname(__file__))))

import time
import numpy as np
from deepface import DeepFace
import matplotlib.pyplot as plt

#################
# Configuration #
#################

# Backends are used to detect regions of the image with faces (if any)
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

# Models are used to perform face recognition (i.e., name-match) on the cropped faces detected by the backend;
# to do this, models convert the crops into fixed-length vectors, then apply a similarity metric to each 
# vector representing (predefined) recognized faces, e.g., if we have faces of:
# - person 1 (with a precomputed vector representing it)
# - person 2 (with a precomputed vector representing it)
# We ask the questions:
# - what is the similarity between the current crop's vector and person 1's?
# - what is the similarity between the current crop's vector and person 2's?
# Then, if any distance (e.g., crop and person 1) is lower than a predefined 
# threshold, we say the crop corresponds to that person
DEEPFACE_MODELS = [
    "VGG-Face",
    "Facenet",
    "Facenet512",
    "OpenFace",
    "DeepID",
    "ArcFace"
]

# cosine similarity = (a·b) / (||a||₂ * ||b||₂) = ( Σᵢ(aᵢ*bᵢ) ) / ( sqrt(Σᵢ(aᵢ*aᵢ)) * sqrt(Σᵢ(bᵢ*bᵢ)) )
# cosine distance = 1 - cosine similarity
# euclidean distance = L2 norm = ||a-b||₂ = sqrt(Σᵢ(aᵢ-bᵢ)²)
# euclidean_l2 = Euclidean distance between L2-normalized embeddings = ||â - b̂||₂, where â = a / ||a||₂ and b̂ = b / ||b||₂
DISTANCE_METRICS = ["cosine", "euclidean", "euclidean_l2"]

# Directory paths for test images and reference database
TEST_IMAGES_PATH = "1_test_images"
DEEPFACE_DATABASE_PATH = "1_database"

# Default threshold information (for reference)
# THRESHOLD = 0.525 # distances < this threshold will be returned by the find function
# Lower values risk false negatives. High values risk getting false positives.
# Different metrics/models need different thresholds
# Defaults are:
# | Model       | Cosine | Euclidean | Euclidean L2 |
# |-------------|--------|-----------|--------------|
# | VGG-Face    | 0.68   | 1.17      | 1.17         |
# | Facenet     | 0.40   | 10        | 0.80         |
# | Facenet512  | 0.30   | 23.56     | 1.04         |
# | ArcFace     | 0.68   | 4.15      | 1.13         |
# | Dlib        | 0.07   | 0.6       | 0.4          |
# | SFace       | 0.593  | 10.734    | 1.055        |
# | OpenFace    | 0.10   | 0.55      | 0.55         |
# | DeepFace    | 0.23   | 64        | 0.64         |
# | DeepID      | 0.015  | 45        | 0.17         |

# Active testing configuration
DEEPFACE_MODEL = DEEPFACE_MODELS[0]     # set a new model, then run the script
DEEPFACE_BACKEND = DEEPFACE_BACKENDS[7] # fastmtcnn for plot_recognition_times(), elsewhere the code loops all backends
DISTANCE_METRIC = DISTANCE_METRICS[0]   # cosine distance

#######################################
# Helper 1: Validate face recognition #
#######################################
def validate_recognition(prediction, test_image_file):
    # extract predicted name from the identity path;
    # the images are as such:
    # Aaron_Eckhart/
    #  - Aaron_Eckhart_0001.jpg
    # Aaron_Guiel/
    #   - Aaron_Guiel_0001.jpg
    # ...
    predicted_name = prediction.split("/")[-1]
    predicted_name = "_".join(predicted_name.split("_")[:-1])
    predicted_name = predicted_name.lower()
    print(f"validate_recognition: predicted name was: {predicted_name}")

    # extract actual name from test image filename
    actual_name = "_".join(test_image_file.split("_")[:-1])
    actual_name = actual_name.lower()
    print(f"validate_recognition: actual name was: {actual_name}")
    
    # return 1 (match) | 0 (mismatch)
    return 1 if predicted_name == actual_name else 0

############################
# Helper 2: Recognize face #
############################
def recognize_face(test_image_path, backend=DEEPFACE_BACKEND):
    try:
        dfs = DeepFace.find(
            img_path=test_image_path,
            db_path=DEEPFACE_DATABASE_PATH,
            model_name=DEEPFACE_MODEL,
            detector_backend=backend,
            distance_metric=DISTANCE_METRIC,
            enforce_detection=False,
            # threshold=THRESHOLD
        )
        # dfs is a list of dataframes, one per face recognized;
        # 1_test_images contain exactly 1 face, so we take
        # the first dataframe
        face = dfs[0]
        # once we have the face, we return its top prediction (DataFrame row)
        return face.iloc[0] if len(face) > 0 else None
    except Exception as e:
        print(f"recognize_face: error recognizing {test_image_path} with model {DEEPFACE_MODEL} and backend {backend}: {str(e)}")

####################################
# Helper 3: Plot recognition times #
####################################
def plot_recognition_times():
    DeepFace.build_model(DEEPFACE_MODEL)
    
    times = []
    test_image_files = sorted([f for f in listdir(TEST_IMAGES_PATH) if isfile(join(TEST_IMAGES_PATH, f))])
    
    # for each test image
    for test_image_file in test_image_files:
        test_image_path = join(TEST_IMAGES_PATH, test_image_file)
        # measure recognition time
        start_time = time.time()
        _ = recognize_face(test_image_path)
        end_time = time.time()
        times.append(end_time - start_time)
    
    # visualize
    plt.figure(figsize=(10, 6))
    plt.bar(range(len(test_image_files)), times, edgecolor="black", color="#4BA081",)
    plt.xlabel("Test Image")
    plt.ylabel("Recognition time (s)")
    plt.title(f"Recognition times for {DEEPFACE_BACKEND} and {DEEPFACE_MODEL}")
    plt.xticks(range(len(test_image_files)), labels=[f.split(".")[0] for f in test_image_files], rotation=90)
    plt.grid(True, which="both", axis="y", linestyle="--", linewidth=0.5)
    plt.tight_layout()
    plt.show()

#####################################
# Helper 4: Plot backend comparison #
#####################################
def plot_backend_comparison(results, test_image_files):
    average_times = [results[backend]["average_time"] for backend in DEEPFACE_BACKENDS]
    correct_predictions = [results[backend]["correct_predictions"] for backend in DEEPFACE_BACKENDS]

    # numeric x positions for backends
    x = np.arange(len(DEEPFACE_BACKENDS))

    # create figure with primary y-axis
    fig, ax1 = plt.subplots()

    # x is backend index, y are correct recognitions
    color = "#4BA081"
    ax1.set_xlabel("Backend")
    ax1.set_ylabel("Correct recognitions", color="black")
    bars = ax1.bar(x, correct_predictions, color=color, edgecolor="black", label="Correct recognitions")
    ax1.tick_params(axis="y", labelcolor="black")
    ax1.set_xticks(x)
    ax1.set_xticklabels(DEEPFACE_BACKENDS, rotation=45, ha="right")
    ax1.set_ylim(0, len(test_image_files))

    # annotate bars with their heights
    for bar in bars:
        height = bar.get_height()
        ax1.annotate(
            f"{height}",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
        )

    # secondary y-axis for average recognition time
    ax2 = ax1.twinx()
    color = "#387761"
    ax2.set_ylabel("Average time (s)", color="black")
    ax2.plot(x, average_times, color=color, marker="o", linestyle="-", linewidth=2, markersize=5)
    ax2.tick_params(axis="y", labelcolor="black")
    ax2.grid(True, which="major", axis="y", linestyle="--", linewidth=0.5)

    ax1.set_title(f"Correct predictions (bars) and average time (lines) for {DEEPFACE_MODEL} and {DISTANCE_METRIC}")
    fig.tight_layout()
    plt.show()

###########################
# Helper 5: Test backends #
###########################
def test_backends():
    backends_results = {}
    test_image_files = sorted([f for f in listdir(TEST_IMAGES_PATH) if isfile(join(TEST_IMAGES_PATH, f))])

    # build model
    DeepFace.build_model(DEEPFACE_MODEL)

    # for each backend
    for backend in DEEPFACE_BACKENDS:
        backend_result = {
            "correct_predictions": 0,
            "times": []
        }
        
        # for each test image
        for test_image_file in test_image_files:
            test_image_path = join(TEST_IMAGES_PATH, test_image_file)
            
            # measure recognition time
            start_time = time.time()
            result = recognize_face(test_image_path, backend=backend)
            end_time = time.time()
            
            # update correct predictions and times
            backend_result["correct_predictions"] += validate_recognition(result["identity"], test_image_file) if result is not None else 0
            backend_result["times"].append(end_time - start_time)

        # calculate average time
        backend_result["average_time"] = np.mean(backend_result["times"])

        # store backend result
        backends_results[backend] = backend_result

    # visualize results
    plot_backend_comparison(backends_results, test_image_files)
    
    for backend in DEEPFACE_BACKENDS:
        print(f"test_backends: backend: {backend}")
        print(f"\ttest_backends: average time: {backends_results[backend]['average_time']:.4f} seconds")
        print(f"\ttest_backends: correct predictions: {backends_results[backend]['correct_predictions']} out of {len(backends_results[backend]['times'])}\n")

########
# Test #
########
if __name__ == "__main__":
    # NOTE: the first time test_backends() is called will take longer as it builds the representation of all faces in 1_database
    # test_backends()
    plot_recognition_times()