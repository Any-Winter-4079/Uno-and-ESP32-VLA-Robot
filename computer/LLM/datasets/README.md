# Notes on `computer/LLM/datasets/`:

## Use Cases

This folder contains:

- `vla_eval_on_benchmark_dataset/images/`, with images for `eval_on_benchmark.py`, in particular:

  - `awaiting_answer/`, to simulate a person awaiting the robot's answer to the question.
  - `correct_and_new_question/`, to simulate a person reacting to a correct answer, and asking a new question.
  - `incorrect_and_new_question`, to simulate a person reacting to an incorrect answer, and asking a new question.

- `vla_eval_on_driving_dataset/images/`, with images for `eval_on_driving.py`, in particular:

  - `0000 - task explanation.jpg`, to simulate a person explaining the task to the robot.
  - `0001 - continue straight.jpg`
  - ...
  - `0047 - continue straight.jpg`, for circuit images to eval the robot's decisions through one full lap.

The purpose is to eval the robot without needing a person to feed (e.g., 1319) questions in real time / put the robot's physical integrity in danger.

- `vla_sft_dataset/`, with:

  - `images/`, including fine-tuning scene images:
    - `scene_0001_hello_world_dialogue/`
    - `scene_0002_code_execution_dialogue/`
    - ...
  - `output/`, with `image_per_turn.json`, that holds the text that goes along with the images for the VLA's SFT.

First, `images/` is to be used by `create_dataset_with_image_per_turn.py`. After creating the JSON, `images/` and `output/images/` are to be used for the SFT of the model (instructions in `computer/LLM/README.md`).

- Finally, `custom_gsm8k.json`, contains 40 'GSM8K-like' questions that can be used with:

  - `CoT_Dec_PAL_tester_v2.py`
  - `CoT_Dec_PAL_tester_v3.py`

Note however `custom_gsm8k.json` is not needed for the robot's execution, belonging to early LLM experiments. Results (from these early prompting/tool use experiments) for the full 1319 GSM8K questions, can be seen in more detail [here](https://github.com/Any-Winter-4079/Prompting-Experiments-2024).
