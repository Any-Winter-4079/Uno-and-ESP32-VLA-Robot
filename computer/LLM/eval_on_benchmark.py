import sys
from os.path import dirname, abspath
project_root = abspath(dirname(dirname(__file__)))
sys.path.insert(0, project_root)
from pathlib import Path
from datetime import datetime
from production import (
    app,
    END_TAG_OPENING,
    END_TAG_CLOSURE,
    FUNCTION_CALLING,
    START_TAG_OPENING,
    START_TAG_CLOSURE,
    CODE_EXECUTION_TIMEOUT,
    EXECUTE_CODE_FUNCTION_NAME,
)

# modal run eval_on_benchmark.py

################################
# Evaluation types and purpose #
################################

# This script allows running the eval in three ways:
# - Regular model, with a normal prompt asking the benchmark question
# - Regular model being fed robot input (<vision>, <audio>, etc.), being explained how to handle it via system prompt, and being passed the benchmark question as transcribed audio
# - SFTed model to work with robot input being passed the benchmark question as transcribed audio

# Its purpose is to:
# - document performance drop, if any, after finetuning to behave as a robot (learns how to behave like a robot, forgets other things)
# - (scalability aside) document performance gain, if any, after alone time researching a topic on 24/7 mode

############################################################
# Memory handling (to avoid contamination on future evals) #
############################################################
# To allow for the saving of memories during evaluation while not compromising future evaluations on this benchmark,
# a special category is given to evaluation memories, to give the model:
# - all previous knowledge
# - the ability to store new knowledge as it's performing the task (and the ability to access it), labeled with
#  a special category, to be deleted after the benchmark is complete.

# Once the benchmark is complete, we keep the original non-contaminated memories. It is as if the eval never happened.
# The only issue is, running 24/7 and getting the current time to feed within <datetime></datetime>, it generates a 
# hole of experiences during the time the evaluation is performed, once the contaminating memories are deleted, e.g.,
# memories are: ..., experiences today 8-9am, experiences today 9-10am;
# evaluation happens today 10am-11am (and memories from 10-11am are stored, but will be deleted)
# the model continues after evaluation, with memories from:
# ..., experiences today 8-9am, experiences today 9-10am
# but it will be 11am already, so the memory will continue as such:
# ..., experiences today 8-9am, experiences today 9-10am, [HOLE], experiences today 11-12pm

# Two options, not implemented here:
# - run the eval on separate hardware, so the model keeps experiencing input and generating output,
#   but a copy of itself is concurrently being evaluated on the benchmark.
# - not feed real time within <datetime></datetime>, but adjust to remove holes. Not recommended 
#   because the model is capable of accessing the internet, and executing Python, and it can see
#   conflicting times

#################
# Configuration #
#################

# Memory category, to delete and restore memory state after benchmarking
EVAL_CATEGORY = f"benchmark_at_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

# Model paths
REGULAR_MODEL_PATH = "Qwen/Qwen3-VL-2B-Instruct"                        # non-SFTed model path (regular Qwen3-VL)
                                                                        # SFTed model path imported from production.py

# Max attempts/turns per question
MAX_TURNS_PER_QUESTION = 2                                              # this includes multiple attempts at a question and tool calls (e.g., calling a tool one turn and getting the result next turn)

# Model choice
USE_SFTED_MODEL = False                                                 # True to use the SFTed model, False to use regular Qwen3-VL

# Working mode choice
USE_ROBOT_BEHAVIOR = True                                               # True for robot-style input (<vision>, <audio>, etc.), False for plain text input

# Dataset
DATASET_NAME = "GSM8K"                                                  # for results file name
DATASET_SPLIT = "test"
DATASET_CONFIG = "socratic"
SEED = 1337                                                             # for reproducibility
N_SAMPLES = None                                                        # to evaluate on fewer than 1319 GSM8K questions
TOTAL_QUESTIONS = N_SAMPLES if N_SAMPLES is not None else 1319
ESTIMATED_SECONDS_PER_QUESTION = (10, 20)                               # e.g., (min: 10 seconds, max: 20 seconds)
ESTIMATED_MIN_HOURS_FOR_EVALUATION = ESTIMATED_SECONDS_PER_QUESTION[0] * TOTAL_QUESTIONS / 3600
ESTIMATED_MAX_HOURS_FOR_EVALUATION = ESTIMATED_SECONDS_PER_QUESTION[1] * TOTAL_QUESTIONS / 3600

# Save folder
RESULTS_FOLDER = (Path(__file__).parent / "results").resolve()

# System prompt
REGULAR_SYSTEM_PROMPT = """You are a helpful assistant"""               # regular Qwen3-VL system prompt
                                                                        # SFTed model system prompt imported from production.py

# For robot behavior:
# Instead of actually being in front of the robot and speaking all of the questions (e.g., 1319 GSM8K questions), we take:
# - 2 images simulating vision awaiting an answer: for the first turn, and for when the model decides to answer in 2 turns
# - 4 images simulating vision after a correct answer, telling it it's correct and asking a new question (if any are left)
# - 4 images simulating vision after an incorrect answer, telling it it's incorrect, and asking a new question (if any are left)
# - an initial transcribed message to be passed within <audio></audio> explaining the benchmark
# - the result of the previous question, and a new question (if any are left)
# The image folders are used to avoid passing the same vision image always. The more variety, the better, but for 3 context turns:
# - ctx_1_correct, ctx_2_correct, ctx_3_correct, current_turn_correct -> 4 correct images maximum
# - ctx_1_incorrect, ctx_2_incorrect, ctx_3_incorrect, current_turn_incorrect -> 4 incorrect images maximum
# - ctx_1_awaiting, ctx_2_correct/incorrect, ctx_3_awaiting, current_turn_correct/incorrect -> 2 awaiting images maximum
# generally 4 correct, 4 incorrect, and 2 awaiting images are okay to avoid repetition

# Initial robot-behavior transcribed audio
# NOTE: From there, it is responsibility of the model to store it or pass it forward in its output to the next turn
# (e.g., to remember the answer must be spoken or what format to use for it, such as 'The answer is X')
ROBOT_BEHAVIOR_FIRST_INPUT_TURN_TRANSCRIBED_AUDIO = ("Hello! Can you complete the following math evaluation, please? "
"It is important you do so now to measure your learning over time. "
"You can continue with your current task, if you were doing something important, later. "
"You can think internally, but must speak a sentence that exactly says \"The answer is X\", where X is the final numeric answer. "
"Coding as you know is also possible, if you need to use it. You will have a maximum of 2 (world) input turns per question. "
"Answer either in the first or in the second, but as soon as you speak \"The answer is X\", that will be your final answer. "
f"There will be a total of {TOTAL_QUESTIONS} questions. "
f"It will take us about {ESTIMATED_MIN_HOURS_FOR_EVALUATION:.2f}-{ESTIMATED_MAX_HOURS_FOR_EVALUATION:.2f} hours total. "
"Good luck! The questions will being shortly.")

# Robot behavior vision
ROBOT_BEHAVIOR_AWAITING_ANSWER_IMAGES_DIR = Path("datasets/vla_eval_on_benchmark_dataset/images/awaiting_answer/")
ROBOT_BEHAVIOR_CORRECT_ANSWER_IMAGES_DIR = Path("datasets/vla_eval_on_benchmark_dataset/images/correct_and_new_question/")
ROBOT_BEHAVIOR_INCORRECT_ANSWER_IMAGES_DIR = Path("datasets/vla_eval_on_benchmark_dataset/images/incorrect_and_new_question/")

# With regular behavior, there is no vision, and the model is reminded of the task every message
# Something that is explained too, is how to execute Python code (in 2 turns), to have the 
# same capabilties as the robot (minus memory saving, which probably adds little to a non-SFTed model)
REGULAR_MODEL_INSTRUCTION = ("Hello! Can you solve the following math problem, please? "
"You can think before you answer, but you must end your message with \"The answer is X\", where X is the final numeric answer. "
"You are given two attempts to solve the problem: "
"If you can solve it directly, work out your solution and write \"The answer is X\"."
"If you think the problem is difficult to work out without coding, you can use Python to help you figure out the answer. "
"You must know, however, that even if you use Python, if you write \"The answer is X\" by accident in your first attempt, that will be your final answer (and no Python code will be run). "
"Similarly, if you forget to write \"The answer is X\" before the second attempt concludes, it will count as a failed answer. "
f"To use Python, you must call {EXECUTE_CODE_FUNCTION_NAME}(code, timeout={CODE_EXECUTION_TIMEOUT}) wrapping the call within {START_TAG_OPENING}{FUNCTION_CALLING}{START_TAG_CLOSURE}{END_TAG_OPENING}{FUNCTION_CALLING}{END_TAG_CLOSURE}. "
f"""
Example with the exact syntax needed:
{START_TAG_OPENING}{FUNCTION_CALLING}{START_TAG_CLOSURE}
[{{"function": "{EXECUTE_CODE_FUNCTION_NAME}", "args": {{"code":"import math\n\ndef main():\n    # Problem: From a group of 12 people, how many different 4 person committees\n    # can be formed? Compute the binomial coefficient C(12, 4).\n    n = 12\n    k = 4\n    combinations = math.comb(n, k)\n    return combinations\n"}}}}]
{END_TAG_OPENING}{FUNCTION_CALLING}{END_TAG_CLOSURE}

Notes:
- To run successfully, name your entry function "main" and return your result. I will add code (for you) before and after your script to capture stdout and stderr, call main() without arguments, and json.dumps() and print() what main() returns so you can access the result on my next message. If you receive an empty stderr, it means no errors occurred and your code ran successfully.
- You can change the timeout for the subprocess that will execute your code, within reason.
- At the time, other languages or multiple script executions (in a single turn) are not supported. To run several functions, call all of them inside the entry function."""
"""

Please know that whether you solve the problem directly (in attempt 1) or decide to use Python, and wait for me to feed you the result of the Python execution will be up to you.

The question is:"""
)

#######################################
# Helper 1: extract and format answer #
#######################################
def extract_and_format_value(input_value):
    if not isinstance(input_value, str):
        input_value = str(input_value)
    reversed_input = input_value[::-1]
    numeric_part_reversed = ""
    found_digit = False
    for char in reversed_input:
        if char.isdigit() or (char == "." and found_digit):
            found_digit = True
            numeric_part_reversed += char
        elif char == "," and found_digit:
            continue
        elif char == "-" and found_digit:
            numeric_part_reversed += char
            break
        elif found_digit:
            break
    numeric_part = numeric_part_reversed[::-1]
    try:
        formatted_value = "{:,.2f}".format(float(numeric_part.replace(",", "")))
        return formatted_value
    except ValueError:
        return "bug"
    
#####################################################
# Helper 2: get image path and increase image index #
#####################################################
def get_image_path_and_increase_index(paths, index):
    # get current image path
    image_path = paths[index]
    # increase index so next image is different
    index = (index + 1) % len(paths)
    return image_path, index

#################################
# Helper 3: log question result #
#################################
def log_question_result(save_path, question_idx, question, dataset_answer, dataset_concise_answer, attempt_results, result):
    with open(save_path, "a") as f:
        f.write("-------------\n")
        f.write(f"Dataset question {question_idx}\n")
        f.write("-------------\n")
        f.write(f"{question}\n\n")

        f.write("-------------\n")
        f.write(f"Dataset answer {question_idx}\n")
        f.write("-------------\n")
        f.write(f"{dataset_answer}\n\n")

        f.write("-------------\n")
        f.write(f"Dataset concise answer {question_idx}\n")
        f.write("-------------\n")
        f.write(f"{dataset_concise_answer}\n\n")

        for attempt_idx, attempt in attempt_results.items():
            prompt_text = attempt.get("prompt_text")
            f.write("-------------\n")
            f.write(f"Prompt {question_idx}.{attempt_idx}\n")
            f.write("-------------\n")
            f.write(f"{prompt_text}\n\n")

            full_response = attempt.get("full_response")
            f.write("-------------\n")
            f.write(f"Full response {question_idx}.{attempt_idx}\n")
            f.write("-------------\n")
            f.write(f"{full_response}\n\n")

            has_function_calls = attempt.get("has_function_calls")
            f.write("-------------\n")
            f.write(f"Has function calls {question_idx}.{attempt_idx}\n")
            f.write("-------------\n")
            f.write(f"{has_function_calls}\n\n")

            function_call_results = attempt.get("function_call_results")
            f.write("-------------\n")
            f.write(f"Function call results {question_idx}.{attempt_idx}\n")
            f.write("-------------\n")
            f.write(f"{function_call_results}\n\n")

            full_response_time = attempt.get("time")
            f.write("-------------\n")
            f.write(f"Time {question_idx}.{attempt_idx}\n")
            f.write("-------------\n")
            f.write(f"{full_response_time}\n\n")

            concise_prediction = attempt.get("concise_prediction")
            f.write("-------------\n")
            f.write(f"Concise prediction {question_idx}.{attempt_idx}\n")
            f.write("-------------\n")
            f.write(f"{concise_prediction}\n\n")

        f.write("-------------\n")
        f.write(f"Result {question_idx}\n")
        f.write("-------------\n")
        f.write(f"{result}\n\n")

###############################
# Helper 4: log final summary #
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
def eval_on_benchmark():
    import time
    import json
    from collections import deque
    from datasets import load_dataset
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
        INTERNAL_THINKING,
        MAX_CONTEXT_TURNS,
        EXECUTE_CODE_FUNCTION_NAME,
        PUSH_MEMORIES_FUNCTION_NAME,
        PULL_MEMORIES_FUNCTION_NAME,
        VLA_MODEL_PATH as SFTED_MODEL_PATH,
        SYSTEM_PROMPT as SFTED_MODEL_ROBOT_SYSTEM_PROMPT,
    )

    try:

        ###########
        # Dataset #
        ###########
        dataset = load_dataset(DATASET_NAME.lower(), DATASET_CONFIG)[DATASET_SPLIT]
        dataset_to_iterate = dataset.shuffle(seed=SEED)
        if N_SAMPLES is not None and N_SAMPLES <= len(dataset):
            dataset_to_iterate = dataset_to_iterate.select(range(N_SAMPLES))

        ###########################
        # Model and system prompt #
        ###########################
        if USE_ROBOT_BEHAVIOR and USE_SFTED_MODEL:
            vlm_or_vla_model_path = SFTED_MODEL_PATH        # robot model
            system_prompt = SFTED_MODEL_ROBOT_SYSTEM_PROMPT # robot system prompt
        elif USE_ROBOT_BEHAVIOR and not USE_SFTED_MODEL:
            vlm_or_vla_model_path = REGULAR_MODEL_PATH      # regular model
            system_prompt = SFTED_MODEL_ROBOT_SYSTEM_PROMPT # robot system prompt
        elif not USE_ROBOT_BEHAVIOR and not USE_SFTED_MODEL:
            vlm_or_vla_model_path = REGULAR_MODEL_PATH      # regular model
            system_prompt = REGULAR_SYSTEM_PROMPT           # regular system prompt
        else:
            raise ValueError("eval_on_benchmark: not(USE_ROBOT_BEHAVIOR) and USE_SFTED_MODEL is not supported.")
        
        #############
        # Save path #
        #############
        if N_SAMPLES is None:
            samples_suffix = "all_samples"
        elif N_SAMPLES == 1:
            samples_suffix = "1_sample"
        else:
            samples_suffix = f"{N_SAMPLES}_samples"
        save_path = RESULTS_FOLDER / (
            f"{vlm_or_vla_model_path.split('/')[-1]}_"
            f"{DATASET_NAME}_"
            f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_"
            f"{'robot_behavior' if USE_ROBOT_BEHAVIOR else 'regular_behavior'}_"
            f"seed_{SEED}_"
            f"{MAX_TURNS_PER_QUESTION}_attempts_{samples_suffix}.txt"
        )
        ###########################################
        # Vision images (only for robot behavior) #
        ###########################################
        if USE_ROBOT_BEHAVIOR:
            awaiting_image_index, correct_image_index, incorrect_image_index = 0, 0, 0
            awaiting_images_paths = sorted([p for p in ROBOT_BEHAVIOR_AWAITING_ANSWER_IMAGES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".jpg"])
            correct_images_paths = sorted([p for p in ROBOT_BEHAVIOR_CORRECT_ANSWER_IMAGES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".jpg"])
            incorrect_images_paths = sorted([p for p in ROBOT_BEHAVIOR_INCORRECT_ANSWER_IMAGES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".jpg"])
            print(f"eval_on_benchmark: found {len(awaiting_images_paths)} awaiting, {len(correct_images_paths)} correct, {len(incorrect_images_paths)} incorrect image paths")

        ##############################################
        # Explain the task (only for robot behavior) #
        ##############################################
        # the task is not explained again for robot behavior (contrary to regular model, regular prompt, where it is explained every turn)
        if USE_ROBOT_BEHAVIOR:
            context = deque(maxlen=MAX_CONTEXT_TURNS)
            image_path, awaiting_image_index = get_image_path_and_increase_index(awaiting_images_paths, awaiting_image_index)
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
                system_prompt=system_prompt,
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

        ###########################
        # Iterate dataset samples #
        ###########################
        for question_idx, sample in enumerate(dataset_to_iterate, start=1):
            print("-"*12)
            print(f"sample {question_idx}")
            # extract question, answer and concise answer from dataset
            question = sample["question"]
            dataset_answer = sample["answer"]
            dataset_concise_answer = extract_and_format_value(dataset_answer.split("####")[-1].strip())
            # initialize attempts results
            attempt_results = {}
            # clear state each question if not robot mode
            if not USE_ROBOT_BEHAVIOR:
                context = deque(maxlen=MAX_CONTEXT_TURNS)
                function_call_results = None

            ###########################
            # Iterate sample attempts #
            ###########################
            for attempt_idx in range(1, MAX_TURNS_PER_QUESTION+1):
                print("-"*12)
                print(f"\tattempt {attempt_idx}/{MAX_TURNS_PER_QUESTION}")
                print("-"*12)
                # time response
                attempt_start_time = time.time()
                
                #####################
                # If robot behavior #
                #####################
                # check what the last attempt's result was (correct/incorrect/tool call/no answer and no tool call) to choose the new image
                if USE_ROBOT_BEHAVIOR:
                    #######################
                    # Choose vision image #
                    #######################
                    if result == "Correct":
                        # if correct, use an image congratulating on the last answer and asking new question, and increase index
                        image_path, correct_image_index = get_image_path_and_increase_index(correct_images_paths, correct_image_index)
                    elif result == "Incorrect":
                        # if incorrect, use an image a bit disappointed in the last answer and asking new question, and increase index
                        image_path, incorrect_image_index = get_image_path_and_increase_index(incorrect_images_paths, incorrect_image_index)
                    else:
                        # if first ever question and first ever attempt, or tool call, use an awaiting answer image, and increase index
                        image_path, awaiting_image_index = get_image_path_and_increase_index(awaiting_images_paths, awaiting_image_index)
                    with open(image_path, "rb") as f:
                        current_turn_image_in_bytes = f.read()

                    ############################
                    # Fetch long term memories #
                    ############################
                    k = PULL_MEMORIES_K
                    l = PULL_MEMORIES_L
                    input_query = [f"I am recognizing these faces: {recognized_faces_str}, and I am hearing: {question}"]
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
                    if attempt_idx == 1:
                        # if first turn: ask the question
                        latest_audio_transcript = f"Question {question_idx} is: {question}"
                    elif attempt_idx == MAX_TURNS_PER_QUESTION:
                        # if last turn: warn the robot it must answer
                        latest_audio_transcript = "This will be your last attempt at this question, so you won't have time to execute code now."
                    else:
                        # anything else: don't speak to the robot
                        latest_audio_transcript = NO_AUDIO_MESSAGE
                    current_turn_input_text = build_vla_current_turn_input_text(
                        True, # vision_success (add image)
                        latest_audio_transcript,
                        recognized_faces,
                        None,
                        long_term_memories,
                        function_call_results=function_call_results
                    )

                #######################
                # If regular behavior #
                #######################
                else:      
                    # With no image and no long term memories
                    ##############################
                    # Build current input's text #
                    ##############################
                    if not function_call_results:
                        # if no function call result and first turn, pass the instruction and the question
                        if attempt_idx == 1:
                            current_turn_input_text = f"{REGULAR_MODEL_INSTRUCTION}\n\n{question}"
                        # if no function call result and not first turn, the model probably rambled on to MAX_NEW_TOKENS; pass a reminder
                        else:
                            current_turn_input_text = f"Sorry, I didn't catch your numerical answer but also didn't see a correctly made function call following the given instructions. Could you provide your answer?"
                            # and if it is the last attempt, notify
                            if attempt_idx == MAX_TURNS_PER_QUESTION:
                                current_turn_input_text += " This will be your last attempt, so you won't have time to execute code now."
                    else:
                        # if function call result, pass the result (instruction and question in context)
                        current_turn_input_text = f"The result of the executed code is:\n\n{json.dumps(function_call_results.get(EXECUTE_CODE_FUNCTION_NAME))}"
                        # and if it is the last attempt, notify
                        if attempt_idx == MAX_TURNS_PER_QUESTION:
                            current_turn_input_text += ". This will be your last attempt, so you won't have time to execute code now."

                #################
                # Run the model #
                #################
                response, prompt_text = run_vla_or_vlm.remote(
                    vlm_or_vla_model_path,
                    context,
                    current_turn_input_text,
                    current_turn_image_in_bytes=current_turn_image_in_bytes if USE_ROBOT_BEHAVIOR else None,
                    system_prompt=system_prompt,
                    return_prompt_text=True
                )
                print(response)

                ######################
                # Parse the response #
                ######################
                # - in robot behavior, for internal thinking, function calling, body control, and current task
                # - in non robot behavior, for function calling
                parsed_response = parse_vla_or_vlm_response(response)
                if USE_ROBOT_BEHAVIOR:
                    current_task = parsed_response.get(CURRENT_TASK) or current_task
                
                ###############################
                # Call functions if requested #
                ###############################
                # - in robot behavior, for code execution, memory pulling, and memory pushing
                # - in non robot behavior, for code execution
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
                    "input_image": current_turn_image_in_bytes if USE_ROBOT_BEHAVIOR else None,
                    "output_text": response
                })

                ##########################################
                # Extract reasoning and potential answer #
                ##########################################
                if USE_ROBOT_BEHAVIOR:
                    # extract reasoning from internal thinking
                    internal_thinking = parsed_response.get(INTERNAL_THINKING)
                    # extract potential VLA answer from speech
                    body_control = parsed_response.get(BODY_CONTROL)
                    if body_control:
                        speech = body_control.get("speak")
                        if speech and "The answer is " in speech:
                            # set robot answer, if speech contains 'The answer is '
                            concise_prediction = extract_and_format_value(speech.split("The answer is ")[-1].strip())
                        else:
                            concise_prediction = None
                    else:
                        concise_prediction = None
                else:
                    # get reasoning from VLM response
                    internal_thinking = response.split("The answer is ")[0].strip()
                    # set VLM answer if response contains 'The answer is '
                    if "The answer is " in response:
                        concise_prediction = extract_and_format_value(response.split("The answer is ")[-1].strip())
                    else:
                        concise_prediction = None

                ############################################################
                # Check against gold answer (if concise prediction exists) #
                ############################################################
                if concise_prediction:
                    # check
                    if concise_prediction == dataset_concise_answer:
                        n_correct +=1
                        result = "Correct"
                    else:
                        result = "Incorrect"
                else:
                    result = None

                #################################
                # Keep track of attempt results #
                #################################
                attempt_end_time = time.time()
                attempt_time = attempt_end_time - attempt_start_time
                total_time += attempt_time
                # save attempt
                attempt_results[attempt_idx] = {
                    "time": round(attempt_time, 2),
                    "has_internal_thinking": internal_thinking is not None,
                    "has_function_calls": function_calls is not None,
                    "function_call_results": json.dumps(function_call_results),
                    "concise_prediction": json.dumps(concise_prediction),
                    "prompt_text": prompt_text,
                    "full_response": response
                }

                ########################################
                # Continue to next attempt or question #
                ########################################
                if concise_prediction:
                    break

            ########################
            # Log question results #
            ########################
            log_question_result(
                save_path,
                question_idx,
                question,
                dataset_answer,
                dataset_concise_answer,
                attempt_results,
                result if result else "Incorrect"
            )

        #####################
        # Log final results #
        #####################
        log_final_summary(
            save_path,
            n_correct/len(dataset_to_iterate),
            total_time,
        )

    except Exception as e:
        print(f"eval_on_benchmark: error: {e}")

    ########################
    # Restore memory state #
    #########################
    finally:
        delete_memories_by_category(EVAL_CATEGORY, debug=True)