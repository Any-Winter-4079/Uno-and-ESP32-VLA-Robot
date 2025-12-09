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
TEST_IMAGES_PATH = "1_test_images"
DEEPFACE_DATABASE_PATH = "1_database"

# Default threshold information (for reference)
# THRESHOLD = 0.525 # distances < this threshold will be returned by the find function
THRESHOLD = None # default
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
DEEPFACE_BACKEND = DEEPFACE_BACKENDS[6] # fastmtcnn for plot_recognition_times(), elsewhere the code loops all backends
DISTANCE_METRIC = DISTANCE_METRICS[0]   # cosine distance

##############################################
# Helper 1: Get top prediction for each face #
##############################################
def get_top_predictions(face_df_list):
    # - the list can have more than one DataFrame if there are multiple faces
    # - one DataFrame per face
    # - each DataFrame has one or more rows, from most likely to least likely while meeting the threshold
    top_predictions = []
    if face_df_list is not None:
        for df in face_df_list:
            if len(df) > 0:
                top_prediction = df.iloc[0]
                top_predictions.append(top_prediction)
    # top prediction for each detected face, so the length of the list
    # depends on the number of faces detected, e.g.,
    # [] -> no faces matched (or no faces above threshold)
    # [p1] -> 1 face, with the best match being p1 (with name in p1["identity"])
    # [p1, p2] -> 2 faces, with the best matches being p1 and p2 (with names in p1["identity"], p2["identity"])
    return top_predictions

#############################
# Helper 2: Recognize faces #
#############################
def recognize_faces(
    image_or_image_path,
    detector_backend=DEEPFACE_BACKEND,
    model_name=DEEPFACE_MODEL,
    distance_metric=DISTANCE_METRIC,
    db_path=DEEPFACE_DATABASE_PATH,
    threshold=THRESHOLD
    ):
    try:
        kwargs = dict(
            img_path=image_or_image_path,
            db_path=db_path,
            model_name=model_name,
            detector_backend=detector_backend,
            distance_metric=distance_metric,
            enforce_detection=False,
        )
        # threshold is not used in benchmark_face_recognition_with_known_faces.py but
        # used in benchmark_face_recognition_with_unknown_and_no_faces.py (which
        # imports recognize_faces), so it is added conditionally
        if threshold is not None:
            kwargs["threshold"] = threshold

        # dfs is a list of dataframes, with several candidates per face;
        dfs = DeepFace.find(**kwargs)
        # keep top candidate per face
        return get_top_predictions(dfs)
    except Exception as e:
        print(f"recognize_faces: error recognizing {image_or_image_path} with model {model_name} and backend {detector_backend}: {str(e)}")
        return []

#######################################
# Helper 3: Validate face recognition #
#######################################
def validate_recognition(predictions, test_image_file):
    # test images are as such:
    # 1_test_images/
    # ├── Aaron_Peirsol_0004.jpg
    # ├── ...
    # the database images are as such:
    # 1_database/
    # ├── Aaron_Eckhart/
    #     ├── Aaron_Eckhart_0001.jpg
    #     ├── ...
    # ├── ...
    # while a prediction is as such:
    # 1_database/Aaron_Peirsol/Aaron_Peirsol_0003.jpg

    # extract predicted name from prediction
    # NOTE: because there is 1 face in test_image_file, there should be 1 result in predictions (and if not, just take the first face)
    identity = predictions[0]["identity"]
    predicted_name = identity.split("/")[-1]
    predicted_name = "_".join(predicted_name.split("_")[:-1])
    predicted_name = predicted_name.lower()
    print(f"validate_recognition: predicted name was: {predicted_name}")

    # extract actual name from test image filename
    actual_name = "_".join(test_image_file.split("_")[:-1])
    actual_name = actual_name.lower()
    print(f"validate_recognition: actual name was: {actual_name}")
    
    # return 1 (match) | 0 (mismatch)
    return 1 if predicted_name == actual_name else 0

####################################
# Helper 4: Plot recognition times #
####################################
def plot_recognition_times(
    test_images_path=TEST_IMAGES_PATH,
    detector_backend=DEEPFACE_BACKEND,
    model_name=DEEPFACE_MODEL,
    distance_metric=DISTANCE_METRIC,
    db_path=DEEPFACE_DATABASE_PATH,
    threshold=THRESHOLD
    ):
    DeepFace.build_model(model_name)
    
    times = []
    test_image_files = sorted([f for f in listdir(test_images_path) if isfile(join(test_images_path, f))])
    
    # for each test image
    for test_image_file in test_image_files:
        test_image_path = join(test_images_path, test_image_file)
        # measure recognition time
        start_time = time.time()
        _ = recognize_faces(
            test_image_path,
            detector_backend=detector_backend,
            model_name=model_name,
            distance_metric=distance_metric,
            db_path=db_path,
            threshold=threshold
            )
        end_time = time.time()
        times.append(end_time - start_time)
    
    # visualize
    plt.figure(figsize=(10, 6))
    plt.bar(range(len(test_image_files)), times, edgecolor="black", color="#4BA081",)
    plt.xlabel("Test Image")
    plt.ylabel("Recognition time (s)")
    plt.title(f"Recognition times for {detector_backend} and {model_name}")
    plt.xticks(range(len(test_image_files)), labels=[f.split(".")[0] for f in test_image_files], rotation=90)
    plt.grid(True, which="both", axis="y", linestyle="--", linewidth=0.5)
    plt.tight_layout()
    plt.show()

#####################################
# Helper 5: Plot backend comparison #
#####################################
def plot_backend_comparison(
    results,
    backends,
    bar_keys,
    bar_labels,
    use_secondary_y_axis_for_time,
    title,
    y_label,
    y_max
    ):
    average_times = [results[backend]["average_time"] for backend in backends]
    bar_values = [[results[backend][key] for backend in backends] for key in bar_keys]

    # numeric x positions for backends
    x = np.arange(len(backends))

    # create figure with primary y-axis
    fig, ax1 = plt.subplots()

    # x is backend index, y are correct recognitions
    colors = ["#4BA081", "#388872", "#83A598"]
    ax1.set_xlabel("Backend")
    ax1.set_ylabel(y_label, color="black")
    ax1.set_title(title)
    ax1.set_xticks(x)
    ax1.set_xticklabels(backends, rotation=45, ha="right")
    ax1.set_ylim(0, y_max)

    # number of bars per x-axis point (or backend, as they are on the x-axis)
    n_bars_per_backend = len(bar_keys)
    bar_width = 0.8 / n_bars_per_backend

    bars_list = []
    for i, values in enumerate(bar_values):
        # evenly distribute bars around the center index
        offset = bar_width * (i - (n_bars_per_backend - 1) / 2)
        bars = ax1.bar(
            x + offset,
            values,
            bar_width,
            color=colors[i % len(colors)],
            edgecolor="black",
            label=bar_labels[i]
        )
        bars_list.append(bars)

    ax1.legend()

    # annotate bars with their heights
    for bars in bars_list:
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

    if use_secondary_y_axis_for_time:
        # secondary y-axis for average recognition time
        ax2 = ax1.twinx()
        color = "#387761"
        ax2.set_ylabel("Average time (s)", color="black")
        ax2.plot(x, average_times, color=color, marker="o", linestyle="-", linewidth=2, markersize=5)
        ax2.tick_params(axis="y", labelcolor="black")
        ax2.grid(True, which="major", axis="y", linestyle="--", linewidth=0.5)

    fig.tight_layout()
    plt.show()

###########################
# Helper 6: Test backends #
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
            recognized_faces = recognize_faces(test_image_path, detector_backend=backend)
            end_time = time.time()
            
            # update correct predictions and times
            backend_result["correct_predictions"] += validate_recognition(recognized_faces, test_image_file) if len(recognized_faces) > 0 else 0
            backend_result["times"].append(end_time - start_time)

        # calculate average time
        backend_result["average_time"] = np.mean(backend_result["times"])

        # store backend result
        backends_results[backend] = backend_result

    # visualize results
    plot_backend_comparison(
        results=backends_results,
        backends=DEEPFACE_BACKENDS,
        bar_keys=["correct_predictions"],
        bar_labels=["Correct predictions"],
        use_secondary_y_axis_for_time=True,
        title=f"Correct predictions (bars) and average time (lines) for {DEEPFACE_MODEL} and {DISTANCE_METRIC}",
        y_label="Correct predictions",
        y_max=len(test_image_files)
    )
    
    # print results
    for backend in DEEPFACE_BACKENDS:
        print(f"test_backends: backend: {backend}")
        print(f"\ttest_backends: average time: {backends_results[backend]['average_time']:.4f} seconds")
        print(f"\ttest_backends: correct predictions: {backends_results[backend]['correct_predictions']} out of {len(backends_results[backend]['times'])}\n")

########
# Test #
########
if __name__ == "__main__":
    # NOTE: the first time test_backends() is called will take longer as it builds the representation of all faces in 1_database
    test_backends()
    plot_recognition_times()