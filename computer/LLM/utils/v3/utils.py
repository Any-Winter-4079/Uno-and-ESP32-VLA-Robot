import re
import os
import time
import random
import tempfile
import subprocess
from config.v3.config import *

def apply_template_replacements(exemplar_contents):
    updated_exemplar_contents = {}
    for key, content in exemplar_contents.items():
        modified_content = content.format(
            system_start=MODEL_TEMPLATE.get("system_start", ""),
            system_message=MODEL_TEMPLATE.get("system_message", ""),
            system_end=MODEL_TEMPLATE.get("system_end", ""),
            user_start=MODEL_TEMPLATE.get("user_start", ""),
            user_lead_message=USER_LEAD_METHOD_TEMPLATES.get(key, ""),
            user_end=MODEL_TEMPLATE.get("user_end", ""),
            assistant_start=MODEL_TEMPLATE.get("assistant_start", ""),
            assistant_end=MODEL_TEMPLATE.get("assistant_end", ""),
        )
        updated_exemplar_contents[key] = modified_content
    return updated_exemplar_contents

def extract_exemplars(file):
    file_content = file.read()

    match = re.search(r'exemplars\s*=\s*"""(.*?)"""', file_content, re.DOTALL)
    if match:
        exemplars = match.group(1)
        return exemplars
    else:
        return file_content
    
def load_exemplars():
    exemplar_contents = {}
    for method_to_test in METHODS_AND_ITERATIONS_PER_METHOD:
        with open(EXEMPLARS_PATHS[method_to_test], 'r') as file:
            if "0Shot" in method_to_test:
                exemplar_contents["0Shot"] = extract_exemplars(file)
            elif "Decl" in method_to_test:
                exemplar_contents["Decl"] = extract_exemplars(file)
            elif "CoTR" in method_to_test:
                exemplar_contents["CoTR"] = extract_exemplars(file)
            elif "CoT" in method_to_test:
                exemplar_contents["CoT"] = extract_exemplars(file)
            elif "PAL" in method_to_test:
                exemplar_contents["PAL"] = extract_exemplars(file)
    if len(METHODS_AND_ITERATIONS_PER_METHOD) > 1:
        with open(LLM_DECIDER_PATH, 'r') as file:
            exemplar_contents["Decider"] =  extract_exemplars(file)
    updated_exemplar_contents = apply_template_replacements(exemplar_contents)
    return updated_exemplar_contents

def extract_and_format_value(input_value):
    if not isinstance(input_value, str):
        input_value = str(input_value)
    reversed_input = input_value[::-1]
    numeric_part_reversed = ""
    found_digit = False
    for char in reversed_input:
        if char.isdigit() or (char == '.' and found_digit):
            found_digit = True
            numeric_part_reversed += char
        elif char == ',' and found_digit:
            continue
        elif char == '-' and found_digit:
            numeric_part_reversed += char
            break
        elif found_digit:
            break
    numeric_part = numeric_part_reversed[::-1]
    try:
        formatted_value = "{:,.2f}".format(float(numeric_part.replace(',', '')))
        return formatted_value
    except ValueError:
        return "bug"

def select_mode_or_sample(concise_pred_frequencies):
    max_frequency = max(concise_pred_frequencies.values())
    modes = [concise for concise, freq in concise_pred_frequencies.items() if freq == max_frequency]
    
    if len(modes) == 1:
        mode = modes[0]
        print(f"\tDecider (mode): {mode}")
        return mode, "mode"
    else:
        # print("\tTie detected: resorting to sampling among modes.")
        weighted_modes = [mode for mode in modes for _ in range(concise_pred_frequencies[mode])]
        choice = random.choice(weighted_modes)
        print(f"\tDecider (sampling): {choice}")
        return choice, "sampling"

def sample_based_on_frequency(unique_valid_concise):
    weighted_answers = [concise for concise, details in unique_valid_concise.items() for _ in range(len(details))]
    choice = random.choice(weighted_answers)
    print(f"\tDecider (sampling): {choice}")
    return choice, "sampling"

def save_results(data_to_save, save_path, duration, n_correct):
    with open(save_path, "w") as file:
        for item in data_to_save:
            sections = [
                ("Question", item["question"]),
                ("Answer", item["answer"]),
                ("Concise answer", item["concise_answer"]),
                ("Prediction", item["prediction"]),
                ("Concise prediction", item["concise_prediction"]),
                ("Result", item["result"])
            ]
            for section_title, section_content in sections:
                file.write("-------------\n")
                file.write(f"{section_title} {item['index']}\n")
                file.write("-------------\n")
                file.write(f"{section_content}\n\n")

        file.write(f"Time: {(duration):.2f} seconds\n")
        n_samples = len(data_to_save)
        file.write(f"Accuracy: {n_correct / n_samples:.3f}\n")

def run_llm(message, stop_list, cpp=False, iteration=0):
    start_time = time.time()
    # print(f"Running LLM with message: {message}")
    if not cpp:
        try:
            prediction = llm(
                message,
                max_tokens=max_tokens, # Set to None to generate up to the end of the context window
                stop=stop_list, # Stop generating just before the model would generate a new question
                temperature=TEMP,
                echo=False # Echo the prompt back in the output. Useful for debugging but False for PAL and SymPy
            )
            prediction = prediction['choices'][0]['text'].strip()
        except Exception as e:
            print(f"run_llm: {e}")
            prediction = "bug"
    else:
        try:
            # command_base = [
            #     "bash", "-c",
            #     f"cd {LLAMA_BASE_PATH} && make -j && ./main -m {str(MODEL_PATHS[MODEL_TO_TEST])} -n {max_tokens} -e -s {seed} --log-disable"
            # ]
            with tempfile.NamedTemporaryFile('w', delete=False) as temp_prompt_file:
                temp_prompt_file.write(message)
                temp_prompt_file_path = temp_prompt_file.name
            command = [
                    "bash", "-c",
                    f"{LLAMA_BASE_PATH}/main -m {str(MODEL_PATHS[MODEL_TO_TEST])} -n {max_tokens} -e -s {seed+iteration} -f {temp_prompt_file_path} -c {CONTEXT_WINDOWS[MODEL_TO_TEST]} -ngl -1 -r {STOP} --prompt-cache prompt_cache_{MODEL_TO_TEST}"
                ]
            # command = [
            #     "bash", "-c",
            #     f"make -j && {LLAMA_BASE_PATH}/parallel -m {str(MODEL_PATHS[MODEL_TO_TEST])} -n {max_tokens} -s {seed+iteration} -f {temp_prompt_file_path} -c {CONTEXT_WINDOWS[MODEL_TO_TEST]} -ngl -1 -np 4 -ns 4 -cb -b 512 -r 'Q:' --prompt-cache prompt_cache"
            # ]
            # ./parallel -m models/mixtral-8x7b-instruct-v0.1/mixtral-8x7b-instruct-q5_0.gguf -n 1024 -t 1 -ngl -1 -c 1024 -b 512 -s 1 -np 4 -ns 4 -cb -p "Are you familiar with the Special Theory of Relativity and can you explain it to me?"
            result = subprocess.run(command, cwd=LLAMA_BASE_PATH, capture_output=True, text=True)
            assistant_start = "<|assistant|>"
            result.stdout = result.stdout.split(assistant_start)[-1]
            result.stdout = result.stdout.replace(message, "").replace("Q:", "").strip()
            os.remove(temp_prompt_file_path)

            if result.returncode == 0:
                prediction = result.stdout
            else:
                print("Error executing command:", result.stderr)
                prediction = "bug"
        except Exception as e:
            print(f"run_llm: {e}")
            prediction = "bug"
        
    end_time = time.time()
    duration = end_time - start_time
    print(f"In {duration:.2f}s:")
    return prediction