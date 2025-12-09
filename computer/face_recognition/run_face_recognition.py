import sys
from os.path import dirname, join, abspath
sys.path.append(abspath(dirname(dirname(__file__))))

import re
import cv2
import time
from deepface import DeepFace
from calibration.store_images_to_calibrate import update_camera_config
from face_recognition.benchmark_face_recognition_with_known_faces import recognize_faces
from depth.calculate_depth_with_depth_anything import get_stereo_images, rectify_left_image, rectify_right_image

#################
# Configuration #
#################

JPEG_QUALITY = 12                                                   # 0-63 (lower means higher quality)
FRAME_SIZE = "FRAMESIZE_VGA"                                        # 640x480 resolution
USE_HOTSPOT = True                                                  # True for phone hotspot, False for home WiFi
RIGHT_EYE_IP = "172.20.10.10" if USE_HOTSPOT else "192.168.1.180"   # ESP32-CAM right eye IP
LEFT_EYE_IP = "172.20.10.11" if USE_HOTSPOT else "192.168.1.181"    # ESP32-CAM left eye IP
STREAM_TIMEOUT = 3                                                  # seconds
CONFIG_TIMEOUT = 5                                                  # seconds

DEEPFACE_DATABASE_PATH = "production_database"
DISTANCE_METRIC = "cosine"                                          # "cosine" | "euclidean" | "euclidean_l2"
DEEPFACE_BACKEND = "fastmtcnn"                                      # detection backend
DEEPFACE_MODEL = "VGG-Face"                                         # recognition model
THRESHOLD = 0.5                                                     # recognition threshold

# Default threshold information (for reference)
# Distances < this threshold will be returned by the find function
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

# camera endpoints
ESP32_RIGHT_IMAGE_URL = f"http://{RIGHT_EYE_IP}/image.jpg"
ESP32_LEFT_IMAGE_URL = f"http://{LEFT_EYE_IP}/image.jpg"
ESP32_LEFT_CONFIG_URL = f"http://{LEFT_EYE_IP}/camera_config"
ESP32_RIGHT_CONFIG_URL = f"http://{RIGHT_EYE_IP}/camera_config"

###################################
# Helper 1: Draw boxes and labels #
###################################
def draw_boxes_and_labels(rectified_image, unique_individuals):
    for person_name, info in unique_individuals.items():
        # extract face coordinates
        x, y, w, h = info["source_x"], info["source_y"], info["source_w"], info["source_h"]
        
        # format the display name by removing numbers and underscores
        identity = person_name
        identity = re.sub(r'_\d+$', "", identity)
        identity = identity.replace("_", " ")
        
        # draw bounding box and name label
        cv2.rectangle(rectified_image, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(rectified_image, identity, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

#################################
# Helper 2: Process predictions #
#################################
def process_predictions(top_predictions, db_path=DEEPFACE_DATABASE_PATH):
    unique_individuals = {}
    for prediction in top_predictions:
        identity_path = prediction["identity"].replace(db_path + "/", "").split("/")
        person_name = identity_path[0]
        if person_name not in unique_individuals:
            unique_individuals[person_name] = prediction
    return unique_individuals

#########################################################
# Main: Run face recognition (using the robot's frames) #
#########################################################
def main():
    ##############
    # Initialize #
    ##############
    # initialize performance metrics
    total_face_recognition_time = 0
    face_recognition_iterations = 0
    # initialize stream state
    stream_to_recover = False

    ###############
    # Build model #
    ###############
    DeepFace.build_model(DEEPFACE_MODEL)

    ################################################
    # Update each ESP32-CAM frame quality and size #
    ################################################
    update_camera_config(ESP32_LEFT_CONFIG_URL, JPEG_QUALITY, FRAME_SIZE, timeout=CONFIG_TIMEOUT)
    update_camera_config(ESP32_RIGHT_CONFIG_URL, JPEG_QUALITY, FRAME_SIZE, timeout=CONFIG_TIMEOUT)

    while True:
        ####################################
        # Handle stream recovery if needed #
        ####################################
        if stream_to_recover:
            print("main: stream is being recovered")
            # if the cameras ever restart and that is the reason why we can't reach them, they will lose our camera
            # config, so send it again (hoping they come back to life)
            update_camera_config(ESP32_LEFT_CONFIG_URL, JPEG_QUALITY, FRAME_SIZE, timeout=CONFIG_TIMEOUT)
            update_camera_config(ESP32_RIGHT_CONFIG_URL, JPEG_QUALITY, FRAME_SIZE, timeout=CONFIG_TIMEOUT)
            # for now, we asume they don't need recovery, and give them a chance, calling get_stereo_images;
            # if it fails, it'll be switched back to True and we will try to send the config once more
            stream_to_recover = False
            # give time to the cameras to recover/process update_camera_config
            cv2.waitKey(1000)
        
        ##################################
        # Fetch images from both cameras #
        ##################################
        left_eye_image, right_eye_image = get_stereo_images(ESP32_LEFT_IMAGE_URL, ESP32_RIGHT_IMAGE_URL)

        ######################################################################################
        # Rectify right image (preferrably), and if not, left image; else, mark for recovery #
        ######################################################################################
        if right_eye_image is not None:
            rectified_image = rectify_right_image(right_eye_image)
        elif left_eye_image is not None:
            rectified_image = rectify_left_image(left_eye_image)
        else:
            print("main: failed to fetch any image within timeout. Starting recovery")
            stream_to_recover = True
            continue

        #####################################
        # Perform and time face recognition #
        #####################################
        face_recognition_start_time = time.time()
        recognized_faces = recognize_faces(
                rectified_image,
                detector_backend=DEEPFACE_BACKEND,
                model_name=DEEPFACE_MODEL,
                distance_metric=DISTANCE_METRIC,
                db_path=DEEPFACE_DATABASE_PATH,
                threshold=THRESHOLD
        )
        face_recognition_end_time = time.time()
        unique_individuals = process_predictions(recognized_faces) if recognized_faces else {}
        total_face_recognition_time += (face_recognition_end_time - face_recognition_start_time)
        face_recognition_iterations += 1
        
        ######################################################
        # Display recognized faces (if any) drawn over image #
        ######################################################
        if unique_individuals:
            draw_boxes_and_labels(rectified_image, unique_individuals)
        cv2.imshow("DeepFace face recognition", rectified_image)
        if cv2.waitKey(50) & 0xFF == ord("q"):
            break
    
    ##############################
    # Report performance metrics #
    ##############################
    if face_recognition_iterations > 0:
        average_face_recognition_time = total_face_recognition_time / face_recognition_iterations
        print(f"main: average face recognition calculation time over {face_recognition_iterations} iterations: {average_face_recognition_time:.3f} seconds")

########
# Test #
########
if __name__ == "__main__":
    main()