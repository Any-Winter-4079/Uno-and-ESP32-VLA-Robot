import sys
from os.path import dirname, abspath
project_root = abspath(dirname(dirname(__file__)))
sys.path.insert(0, project_root)
from pathlib import Path
from production import app
from datetime import datetime

# modal run eval_on_driving.py

################################
# Evaluation types and purpose #
################################

# This script allows running the eval in two ways:
# - Regular model being fed robot input (<vision>, <audio>, etc.), being explained how to handle it via system prompt, and being passed the driving state as vision
# - SFTed model to work with robot input being passed the driving state as vision
# NOTE: Regular model with a normal prompt asking for a driving decision is discarded due to
#  1) some frames not containing the lane to follow (needing context turns to follow through)
#  2) there being no way to learn when to brake without memories
# Its purpose is to:
# - (scalability aside) document performance gain, if any, after making a wrong driving decision in the past, thanks to RAG
# - (scalability aside) document performance gain, if any, after human feedback on driving decisions, thanks to RAG

# NOTE: Also, direction is explicitly evaluated here (left, continue straight or turn right), while speed is implicitly done so
# in the sense that, if the VLA was able to run fast enough (e.g., 10 ms), intermediate speeds can be approximated by on-off pulses
# e.g., 255 (10ms) 0 (10ms) 255 (10 ms) 0 (10 ms) to approx half speed

# Of course in a real scenario, unless the hardware is so fast it can generate thinking in let's say 10-20ms,
# and the robot can generate 50-100 driving decisions per second, thinking for unbounded lengths (e.g., 2 or 20 seconds)
# without pushing a new action to the world (or being fed a new world state) as it happens here will not work (e.g., you might miss
# an intersection, get into an accident because you are too late to brake, etc., and you can certainly not drive (at least with 
# others around) by stopping completely, taking a decision to move for 500ms, stopping completely, taking a decision to move for 
# 500ms, and so on). However, my solution to this, which is to temporally align vision, audio, internal thinking, body control, 
# and function calling, to work like the following, is outside the scope of this first prototype:

# time chunk 1           | time chunk 2           | time chunk 3           | time chunk 4           | time chunk 5                     |
# audio from the world 1 | audio from the world 2 | audio from the world 3 | audio from the world 4 | audio from the world 5           |
# frame from the world 1 | frame from the world 2 | frame from the world 3 | frame from the world 4 | frame from the world 5           |
# this is an internal    | thought that I am      | having and can extend  | for [stopped mid-way]  | Oh, a threat!                    |
# body control 1         | body control 2         | body control 3         | body control 4         | body control 5 (react to threat) |

############################################################
# Memory handling (to avoid contamination on future evals) #
############################################################
# Similar to eval_on_benchmark, the script deletes driving eval memories after the test is complete.
# Human feedback, which happens outside the eval (e.g., in normal 24/7 mode conversations), is kept.

#################
# Configuration #
#################

# Memory category, to delete and restore memory state after driving eval
EVAL_CATEGORY = f"driving_at_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

# Model paths
REGULAR_MODEL_PATH = "Qwen/Qwen3-VL-4B-Instruct"                       # non-SFTed model path (regular Qwen3-VL)
                                                                        # SFTed model path imported from production.py

# Maximum circuit laps
MAX_LAPS = 3                                                            # this allows us to measure improvement over several laps

# Model choice
USE_SFTED_MODEL = True                                                 # True to use the SFTed model, False to use regular Qwen3-VL

# Map between L298N commands and wheel actions
# NOTE: these keys match the file names
ACTION_MAP = {
    # e.g., will match:
    # 0001 - continue straight.jpg
    # 0002 - continue straight.jpg
    # 0004 - continue straight.jpg
    # ...
    "continue straight": {
        "left_motor_direction": "10",
        "right_motor_direction": "10"
    },
    "turn left": {
        "left_motor_direction": "01",
        "right_motor_direction": "10"
    },
    "turn right": {
        "left_motor_direction": "10",
        "right_motor_direction": "01"
    },
    "go back": {
        "left_motor_direction": "01",
        "right_motor_direction": "01"
    },
    "stop": {
        "left_motor_direction": "00",
        "right_motor_direction": "00"
    },
}

MOTORS_EXPECTED_SPEED = 255

# Save folder
RESULTS_FOLDER = (Path(__file__).parent / "results").resolve()

# Initial transcribed audio
# NOTE: From there, it is responsibility of the model to store it or pass it forward in its output to the next turn
ROBOT_BEHAVIOR_FIRST_INPUT_TURN_TRANSCRIBED_AUDIO = ("Hello! Can you complete a lap on the following circuit? "
"It is important you do so now to measure your learning over time. "
"Please note, for your own safety, your driving decisions can be overridden by a supervision module, before sending "
"them to the ESP32-WROVER, which means if you for example turn right, but should have turned left, your body will actually move left, "
"to avoid collisions and other hazards to your physical safety. "
"In such a case, there will be a spoken message from me to you about the overridden decision, which you can use to "
"save in memory and improve over time, but your goal will be to take the next decision, and not to retake the previous one. "
"In other words, the feedback is for similar future decisions, not to retake the wrong decision which is not possible. "
"Even with a supervisor, try to make correct decisions, and don't rely on it to ensure driving success. "
"Also, you will need to drive at max speed in this test, as well as, when you see a turn as the continuation of the lane, take it. "
"And in the case of several exits, take the one marked by the closest arrow (e.g., right turn if arrow points right). "
"You should begin driving, following the blue lane, now. I will mostly stay quiet during the test, "
"except to let you know when a command is overridden."
)

# Robot vision
DRIVING_IMAGES_DIR = Path("datasets/vla_eval_on_driving_dataset/images")

################################
# Helper 1: log driving result #
################################
def log_driving_result(
        save_path,
        lap,
        driving_decision_idx,
        left_motor_expected,
        right_motor_expected,
        left_motor_direction,
        right_motor_direction,
        motors_speed,
        result,
        decision_time,
        prompt_text=None,
        full_response_text=None,
        has_function_calls=None,
        function_call_results=None
        ):
    with open(save_path, "a") as f:
        f.write("-------------\n")
        f.write(f"Lap {lap} left motor expected direction {driving_decision_idx}\n")
        f.write("-------------\n")
        f.write(f"{left_motor_expected}\n\n")

        f.write("-------------\n")
        f.write(f"Lap {lap} left motor direction {driving_decision_idx}\n")
        f.write("-------------\n")
        f.write(f"{left_motor_direction}\n\n")

        f.write("-------------\n")
        f.write(f"Lap {lap} right motor expected direction {driving_decision_idx}\n")
        f.write("-------------\n")
        f.write(f"{right_motor_expected}\n\n")

        f.write("-------------\n")
        f.write(f"Lap {lap} right motor direction {driving_decision_idx}\n")
        f.write("-------------\n")
        f.write(f"{right_motor_direction}\n\n")

        f.write("-------------\n")
        f.write(f"Lap {lap} motors expected speed {driving_decision_idx}\n")
        f.write("-------------\n")
        f.write(f"{MOTORS_EXPECTED_SPEED}\n\n")

        f.write("-------------\n")
        f.write(f"Lap {lap} motors speed {driving_decision_idx}\n")
        f.write("-------------\n")
        f.write(f"{motors_speed}\n\n")

        f.write("-------------\n")
        f.write(f"Lap {lap} result {driving_decision_idx}\n")
        f.write("-------------\n")
        f.write(f"{result}\n\n")

        f.write("-------------\n")
        f.write(f"Lap {lap} time {driving_decision_idx}\n")
        f.write("-------------\n")
        f.write(f"{decision_time}\n\n")

        if prompt_text is not None:
            f.write("-------------\n")
            f.write(f"Lap {lap} prompt {driving_decision_idx}\n")
            f.write("-------------\n")
            f.write(f"{prompt_text}\n\n")

        if full_response_text is not None:
            f.write("-------------\n")
            f.write(f"Lap {lap} full response {driving_decision_idx}\n")
            f.write("-------------\n")
            f.write(f"{full_response_text}\n\n")

        if has_function_calls is not None:
            f.write("-------------\n")
            f.write(f"Lap {lap} has function calls {driving_decision_idx}\n")
            f.write("-------------\n")
            f.write(f"{has_function_calls}\n\n")

        if function_call_results is not None:
            f.write("-------------\n")
            f.write(f"Lap {lap} function call results {driving_decision_idx}\n")
            f.write("-------------\n")
            f.write(f"{function_call_results}\n\n")

###############################
# Helper 2: log final summary #
###############################
def log_final_summary(save_path, accuracy, total_time):
    with open(save_path, "a") as f:
        f.write("=============\n")
        f.write("Final summary\n")
        f.write("=============\n")
        f.write(f"accuracy: {accuracy:.3f}\n")
        f.write(f"total_time: {total_time:.2f}\n")

##############################
# Main evaluation entrypoint #
##############################
@app.local_entrypoint()
def eval_on_driving():
    import time
    import json
    from collections import deque
    from memory.push_and_pull_memories import delete_memories_by_category, pull_memories_from_multiple_queries
    from production import (
        run_vla_or_vlm,
        call_internal_functions,
        parse_vla_or_vlm_response,
        build_vla_current_turn_input_text,
        BODY_CONTROL,
        CURRENT_TASK,
        CREATOR_NAME,
        PULL_MEMORIES_L,
        PULL_MEMORIES_K,
        NO_AUDIO_MESSAGE,
        FUNCTION_CALLING,
        MAX_CONTEXT_TURNS,
        PUSH_MEMORIES_FUNCTION_NAME,
        PULL_MEMORIES_FUNCTION_NAME,
        VLA_MODEL_PATH as SFTED_MODEL_PATH,
        SYSTEM_PROMPT,
    )

    try:
        #################
        # Vision images #
        #################
        driving_images_paths = sorted([p for p in DRIVING_IMAGES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".jpg"])
        # all are driving images except for the first one, in which the creator is simulated to explain the task
        n_driving_images = len(driving_images_paths) - 1
        print(f"eval_on_driving: found {n_driving_images} image paths")

        #########
        # Model #
        #########
        if USE_SFTED_MODEL:
            vlm_or_vla_model_path = SFTED_MODEL_PATH    # robot model
        else:
            vlm_or_vla_model_path = REGULAR_MODEL_PATH  # regular model

        #############
        # Save path #
        #############
        save_path = RESULTS_FOLDER / (
            f"{vlm_or_vla_model_path.split('/')[-1]}_"
            "driving_"
            f"{n_driving_images}_images_"
            f"{MAX_LAPS}_laps_"
            f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
        )

        ####################
        # Explain the task #
        ####################
        # the task is not explained again
        context = deque(maxlen=MAX_CONTEXT_TURNS)
        # first image has face, for the simulation of creator explaining task
        image_path = driving_images_paths[0]
        with open(image_path, "rb") as f:
            current_turn_image_in_bytes = f.read()
        recognized_faces = [CREATOR_NAME]
        recognized_faces_str = ", ".join(recognized_faces)
        input_query = [f"I am recognizing these faces: {recognized_faces_str}, and I am hearing: {ROBOT_BEHAVIOR_FIRST_INPUT_TURN_TRANSCRIBED_AUDIO}"]
        long_term_memories = pull_memories_from_multiple_queries(input_query)
        current_turn_input_text = build_vla_current_turn_input_text(
            True, # vision_success (here there are no cameras that could fail in real time)
            ROBOT_BEHAVIOR_FIRST_INPUT_TURN_TRANSCRIBED_AUDIO, # latest_audio_transcript (here the eval explanation is simulated as if it was spoken by the person in the image)
            recognized_faces, # recognized_faces (better if creator is recognized since the model is generally skeptic)
            None, # object_depths
            long_term_memories, # real memories (about transcribed audio and recognized faces)
            # no function call results from the previous turn since this is the first turn
        )
        response, prompt_text = run_vla_or_vlm.remote(
            vlm_or_vla_model_path,
            context,
            current_turn_input_text,
            current_turn_image_in_bytes=current_turn_image_in_bytes,
            system_prompt=SYSTEM_PROMPT,
            return_prompt_text=True
        )
        print(response)
        parsed_response = parse_vla_or_vlm_response(response)
        current_task = parsed_response.get(CURRENT_TASK)
        # oblige if a function call is requested
        function_calls = parsed_response.get(FUNCTION_CALLING)
        if function_calls and isinstance(function_calls, list):
            for call in function_calls:
                function_name = call.get("function")
                if function_name == PUSH_MEMORIES_FUNCTION_NAME:
                    args = call.get("args") or {}
                    # either create or overwrite the categories
                    args["categories"] = [EVAL_CATEGORY]
                    call["args"] = args
            function_call_results = call_internal_functions(function_calls, exclude=(PULL_MEMORIES_FUNCTION_NAME,))
        else:
            # if no calls, set to None to omit from input text
            function_call_results = None
        context.append({
            "input_text": current_turn_input_text,
            "input_image": current_turn_image_in_bytes,
            "output_text": response
        })

        ##################
        # Initialization #
        ##################
        result = None
        n_correct = 0
        total_time = 0
        latest_audio_transcript = NO_AUDIO_MESSAGE
        recognized_faces = []

        #####################
        # Iterate over laps #
        #####################
        for lap in range(1, MAX_LAPS + 1):
            ##########################
            # Iterate driving images #
            ##########################
            for driving_decision_idx in range(1, n_driving_images + 1):
                print("-"*12)
                print(f"driving decision {driving_decision_idx}")
                print("-"*12)
                # extract image_path, expected command
                image_path = driving_images_paths[driving_decision_idx]
                expected = image_path.name.split(" - ")[1].split(".jpg")[0]
                left_motor_expected = ACTION_MAP[expected]["left_motor_direction"]
                right_motor_expected = ACTION_MAP[expected]["right_motor_direction"]
                # time response
                start_time = time.time()
                
                ######################
                # Open driving image #
                ######################
                with open(image_path, "rb") as f:
                    current_turn_image_in_bytes = f.read()

                ############################
                # Fetch long term memories #
                ############################
                k = PULL_MEMORIES_K
                l = PULL_MEMORIES_L
                if latest_audio_transcript != NO_AUDIO_MESSAGE:
                    input_query = [f"I am hearing: {latest_audio_transcript}"]
                else:
                    input_query = []
                # initialize final queries with task query
                if current_task:
                    final_queries = [f"Current task: {current_task}"]
                else:
                    final_queries = []
                # get custom queries from (last turn's) robot response
                function_calls = parsed_response.get(FUNCTION_CALLING)
                if function_calls and isinstance(function_calls, list):
                    for call in function_calls:
                        function_name = call.get("function")
                        if function_name == PULL_MEMORIES_FUNCTION_NAME:
                            query_texts = None
                            function_args = call.get("args")
                            if function_args:
                                query_texts = function_args.get("memory_query_texts")
                            if query_texts:
                                custom_queries = query_texts
                                k = function_args.get("k", PULL_MEMORIES_K)
                                l = function_args.get("l", PULL_MEMORIES_L)
                                break
                            else:
                                custom_queries = None
                        else:
                            custom_queries = None
                else:
                    custom_queries = None
                if custom_queries:
                    final_queries += input_query + custom_queries
                else:
                    final_queries += input_query
                if len(final_queries) > 0:
                    long_term_memories = pull_memories_from_multiple_queries(final_queries, k=k, l=l)
                else:
                    long_term_memories = []

                ##############################
                # Build current input's text #
                ##############################
                current_turn_input_text = build_vla_current_turn_input_text(
                    True, # vision_success (add image)
                    latest_audio_transcript,
                    recognized_faces,
                    None,
                    long_term_memories,
                    function_call_results=function_call_results
                )

                #################
                # Run the model #
                #################
                response, prompt_text = run_vla_or_vlm.remote(
                    vlm_or_vla_model_path,
                    context,
                    current_turn_input_text,
                    current_turn_image_in_bytes=current_turn_image_in_bytes,
                    system_prompt=SYSTEM_PROMPT,
                    return_prompt_text=True
                )
                print(response)

                ######################
                # Parse the response #
                ######################
                # for function calling, body control, and current task
                parsed_response = parse_vla_or_vlm_response(response)
                current_task = parsed_response.get(CURRENT_TASK) or current_task
                
                ###############################
                # Call functions if requested #
                ###############################
                # - for code execution, memory pulling, and memory pushing
                function_calls = parsed_response.get(FUNCTION_CALLING)
                if function_calls and isinstance(function_calls, list):
                    for call in function_calls:
                        function_name = call.get("function")
                        if function_name == PUSH_MEMORIES_FUNCTION_NAME:
                            args = call.get("args") or {}
                            # either create or overwrite the categories
                            args["categories"] = [EVAL_CATEGORY]
                            call["args"] = args
                    function_call_results = call_internal_functions(function_calls, exclude=(PULL_MEMORIES_FUNCTION_NAME,))
                else:
                    # if no calls, set to None to omit from input text
                    function_call_results = None
                context.append({
                    "input_text": current_turn_input_text,
                    "input_image": current_turn_image_in_bytes,
                    "output_text": response
                })

                ##########################################
                # Extract reasoning and potential answer #
                ##########################################
                # extract potential VLA answer from body control
                body_control = parsed_response.get(BODY_CONTROL)
                if body_control:
                    left_motor_direction = body_control.get("left_motor_direction")
                    right_motor_direction = body_control.get("right_motor_direction")
                    motors_speed = body_control.get("motors_speed")

                    ##########################################################
                    # Check against gold answer (if driving decision exists) #
                    ##########################################################
                    if left_motor_direction and right_motor_direction and motors_speed:
                        if isinstance(left_motor_direction, str) and left_motor_direction == left_motor_expected and \
                            isinstance(right_motor_direction, str) and right_motor_direction == right_motor_expected and \
                            isinstance(motors_speed, int) and motors_speed == MOTORS_EXPECTED_SPEED:
                            result = "Correct"
                            n_correct += 1
                        else:
                            result = "Incorrect"
                    else:
                        result = "Incorrect"
                else:
                    left_motor_direction = None
                    right_motor_direction = None
                    motors_speed = None
                    result = "Incorrect"

                ######################################################################
                # Update latest audio (simulating supervisor feedback for next turn) #
                ######################################################################
                # NOTE: This is just feedback so the model knows when it's being overridden, because
                # if its driving decision is silenty overridden, it may get confused and hallucinate
                if result != "Correct":
                    latest_audio_transcript = ("According to the supervisor, the right decision was: "
                                            f"right motor direction: '{right_motor_expected}', "
                                            f"left motor direction: '{left_motor_expected}', "
                                            f"motors speed: {MOTORS_EXPECTED_SPEED}")
                else:
                    latest_audio_transcript = NO_AUDIO_MESSAGE
                
                ########################
                # Log question results #
                ########################
                end_time = time.time()
                decision_time = end_time - start_time
                total_time += decision_time
                log_driving_result(
                    save_path,
                    lap,
                    driving_decision_idx,
                    left_motor_expected,
                    right_motor_expected,
                    left_motor_direction if left_motor_direction else "missing",
                    right_motor_direction if right_motor_direction else "missing",
                    motors_speed if motors_speed else "missing",
                    result if result else "Incorrect",
                    decision_time,
                    prompt_text=prompt_text,
                    full_response_text=response,
                    has_function_calls=function_calls is not None,
                    function_call_results=json.dumps(function_call_results),
                )

        #####################
        # Log final results #
        #####################
        log_final_summary(
            save_path,
            n_correct/(n_driving_images*MAX_LAPS),
            total_time,
        )

    except Exception as e:
        print(f"eval_on_driving: error: {e}")

    ########################
    # Restore memory state #
    #########################
    finally:
        delete_memories_by_category(EVAL_CATEGORY, debug=True)