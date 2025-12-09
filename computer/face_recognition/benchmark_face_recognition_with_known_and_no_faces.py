import sys
from os import listdir
from os.path import dirname, join, isfile, abspath
sys.path.append(abspath(dirname(dirname(__file__))))

import time
import numpy as np
from deepface import DeepFace
import matplotlib.pyplot as plt
from face_recognition.benchmark_face_recognition_with_known_faces import (
    recognize_faces,
    plot_backend_comparison,
    plot_recognition_times
)

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
    # "fastmtcnn",
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
TEST_IMAGES_PATH = "2_test_images"
DEEPFACE_DATABASE_PATH = "2_database"

# Default threshold information (for reference)
THRESHOLD = 0.325 # distances < this threshold will be returned from the find function
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
DEEPFACE_MODEL = DEEPFACE_MODELS[2]     # set a new model, then run the script
DEEPFACE_BACKEND = DEEPFACE_BACKENDS[6] # fastmtcnn for plot_recognition_times(), elsewhere the code loops all backends
DISTANCE_METRIC = DISTANCE_METRICS[0]   # cosine distance

#######################################
# Helper 1: Validate face recognition #
#######################################
def validate_recognition(predictions, test_image_file):
    # test images are as such:
    # 2_test_images/
    # ├── Arnold_Schwarzenegger_front_close_known_0001.png
    # ├── Arnold_Schwarzenegger_front_far_known_0002.png
    # ├── Arnold_Schwarzenegger_side_close_known_0003.png
    # ├── Arnold_Schwarzenegger_side_far_known_0004.png
    # ├── unknown_0001.png
    # ├── ...
    # the database images are as such:
    # 2_database/
    # ├── Aaron_Eckhart/
    #     ├── Aaron_Eckhart_0001.jpg
    #     ├── ...
    # ├── ...
    # while a prediction is as such:
    # 2_database/anders_fogh_rasmussen/anders_fogh_rasmussen

    correct_identification = False
    correct_non_identification = False
    identification_types = {
        "front_close": 0,
        "front_far": 0,
        "side_close": 0,
        "side_far": 0,
    }

    # extract type from test image filename
    if len(test_image_file.split("_")) > 2:
        # e.g., keep front, close, remove Arnold Schwarzenegger, known, 0001.png
        identification_type = "_".join(test_image_file.split("_")[-4:-2])
    else:
        # e.g., unknown_0001.png
        identification_type = None

    # extract actual name from test image filename
    actual_is_unknown = "unknown" in test_image_file
    if actual_is_unknown:
        actual_name = "unknown"
    else:
        # e.g., keep Arnold Schwarzenegger, remove front, close, known, 0001.png
        actual_name = "_".join(test_image_file.split("_")[:-4])
        actual_name = actual_name.lower()
    print(f"validate_recognition: actual name was: {actual_name}")

    # if no face is predicted to be present
    if not predictions:
        predicted_name = "unknown"
        if actual_is_unknown:
            correct_non_identification = True

    # if a face is predicted to be present 
    elif predictions:
        # extract predicted name from prediction
        # NOTE: because there is at most 1 face in test_image_file, there should be 1 result in predictions (and if not, just take the first face)
        identity = predictions[0]["identity"]
        predicted_name = identity.split("/")[-1]
        predicted_name = "_".join(predicted_name.split("_")[:-1])
        predicted_name = predicted_name.lower()
        if predicted_name == actual_name:
            correct_identification = True
            identification_types[identification_type] += 1
    print(f"validate_recognition: predicted name was: {predicted_name}")

    return correct_identification, correct_non_identification, identification_types

###########################
# Helper 2: Test backends #
###########################
def test_backends():
    backends_results = {}
    test_image_files = sorted([f for f in listdir(TEST_IMAGES_PATH) if isfile(join(TEST_IMAGES_PATH, f))])

    # pre-compute expected counts for y-limit in plotting
    type_counts = {
        "front_close": 0,
        "front_far": 0,
        "side_close": 0,
        "side_far": 0,
    }
    n_to_identify = 0
    n_to_not_identify = 0
    for test_image_file in test_image_files:
        if "unknown" in test_image_file:
            n_to_not_identify += 1
        else:
            n_to_identify +=1
        identification_type = "_".join(test_image_file.split("_")[-4:-2])
        if identification_type in type_counts:
            type_counts[identification_type] += 1
    
    # build model
    DeepFace.build_model(DEEPFACE_MODEL)

    # for each backend
    for backend in DEEPFACE_BACKENDS:
        backend_result = {
            "correct_identifications": 0,
            "correct_non_identifications": 0,
            "front_close": 0,
            "front_far": 0,
            "side_close": 0,
            "side_far": 0,
            "times": []
        }
        
        # for each test image
        for test_image_file in test_image_files:
            test_image_path = join(TEST_IMAGES_PATH, test_image_file)

            # measure recognition time
            start_time = time.time()
            recognized_faces = recognize_faces(
                test_image_path,
                detector_backend=backend,
                model_name=DEEPFACE_MODEL,
                distance_metric=DISTANCE_METRIC,
                db_path=DEEPFACE_DATABASE_PATH,
                threshold=THRESHOLD
            )
            end_time = time.time()
            
            # update correct predictions and times
            correct_identification, correct_non_identification, identification_types = validate_recognition(recognized_faces, test_image_file)
            backend_result["correct_identifications"] += correct_identification
            backend_result["correct_non_identifications"] += correct_non_identification
            for id_type in identification_types:
                # backend_result["identification_types"][id_type] += identification_types[id_type]
                backend_result[id_type] += identification_types[id_type]
            backend_result["times"].append(end_time - start_time)
        
        # calculate average time
        backend_result["average_time"] = np.mean(backend_result["times"])

        # store backend result
        backends_results[backend] = backend_result

    # visualize results
    plot_backend_comparison(
        results=backends_results,
        backends=DEEPFACE_BACKENDS,
        bar_keys=["correct_identifications", "correct_non_identifications"],
        bar_labels=["Correct identifications", "Correct non-identifications"],
        use_secondary_y_axis_for_time=False,
        title=f"Recognition performance for {DEEPFACE_MODEL} and {DISTANCE_METRIC}",
        y_label="Number of correct predictions",
        y_max=max(n_to_identify, n_to_not_identify)+1
    )

    plot_backend_comparison(
        results=backends_results,
        backends=DEEPFACE_BACKENDS,
        bar_keys=["front_close", "front_far", "side_close", "side_far"],
        bar_labels=["Front close correct", "Front far correct", "Side close correct", "Side far correct"],
        use_secondary_y_axis_for_time=False,
        title=f"Counts per image type for {DEEPFACE_MODEL} and {DISTANCE_METRIC}",
        y_label="Counts",
        y_max=max(type_counts.values())+1
    )

    # print summary results
    for backend in DEEPFACE_BACKENDS:
        print(f"test_backends: backend: {backend}")
        print(f"\ttest_backends: average time: {backends_results[backend]['average_time']:.4f} seconds")
        print(f"\ttest_backends: correct identifications: {backends_results[backend]['correct_identifications']}")
        print(f"\ttest_backends: correct non-identifications: {backends_results[backend]['correct_non_identifications']}\n")

########
# Test #
########
if __name__ == "__main__":
    # NOTE: the first time test_backends() is called will take longer as it builds the representation of all faces in 2_database
    test_backends()
    plot_recognition_times(
        test_images_path=TEST_IMAGES_PATH,
        detector_backend=DEEPFACE_BACKEND,
        model_name=DEEPFACE_MODEL,
        distance_metric=DISTANCE_METRIC,
        db_path=DEEPFACE_DATABASE_PATH,
        threshold=THRESHOLD
    )