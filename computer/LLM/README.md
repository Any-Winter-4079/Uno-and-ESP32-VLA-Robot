# Notes on the `LLM/` code:

## Computer Setup

Once:

- `arduino/production.ino`
- `esp32/cam/aithinker-production.ino`
- `esp32/cam/m5stackwide-production.ino`
- `esp32/wrover/production.ino`

have been flashed to the Arduino Uno, ESP32-CAMs and ESP32-WROVER.

Once all of the test sketches and scripts have been run and all instructions followed, having added:

- `depth_and_face_recognition/coco.names`
- `depth_and_face_recognition/yolov8n.pt`
- `face_recognition/production_database/`
- `LMM/.env` with:
  - OPENAI_API_KEY=yourKey
- `audio/cloning_voice/`

And having created -via running scripts-:

- `undistortion_and_rectification/stereo_maps/`

Clone `face_recognition/production_database` into `LLM/production_database`

[Then only if you want to run the prompting experiments locally]

Clone llama.cpp into `computer/LLM` and `git checkout` the same commit if needed (else move to `SFT Dataset Creation`):

```
cd computer/LLM
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
git checkout 213701b5
```

Place your model(s) under `llama.cpp/models`, e.g.:

```
llama.cpp/models/Phi-3-mini-4k-instruct-gguf/Phi-3-mini-4k-instruct-fp16.gguf
llama.cpp/models/Phi-3-mini-4k-instruct-gguf/Phi-3-mini-4k-instruct-q4.gguf
```

And test running the model(s):

```
make -j && ./llama-cli -m models/Phi-3-mini-4k-instruct-gguf/Phi-3-mini-4k-instruct-fp16.gguf -p "Building a website can be done in 10 simple steps:\nStep 1:" -n 400 -e
```

## CoT/Dec/PAL/etc. Prompting Tests

Then, to test prompting methods, run:

```
python CoT_Dec_PAL_tester_v1.py
python CoT_Dec_PAL_tester_v2.py
python CoT_Dec_PAL_tester_v3.py
```

## SFT Dataset Creation

To create the VLA SFT dataset (images under `images/`, and `image_per_turn.json` with the conversation), run:

```
python create_dataset_with_image_per_turn.py
```

## SFT on RunPod

### Create `hf_user` and `hf_token` as secrets to push the SFT'ed model to HuggingFace

On RunPod:

1. Click `Secrets` (left sidebar)
2. Click `+ Create Secret`
3. Type `hf_user` as Secret Name
4. Paste or type your Hugging Face username as Secret Value
5. Click Create Secret (to create the secret)
6. Click `+ Create Secret`
7. Type `hf_token` as Secret Name
8. Paste or type your Hugging Face token as Secret Value
9. Click Create Secret (to create the secret)

### Create a RunPod template

The template config is:

1. Container Image: anywinter4079/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04-runpod-clone
2. Container Disk: 250 GB
3. Volume Disk: 500 GB
4. Volume Mount Path: /workspace
5. TCP Ports (max 10): Port label: SSH, Port number: 22

### Deploy the template, setting `hf_user` and `hf_token` as Environment variables

Note `hf_user` and `hf_token` are added as Environment variables on the deployment page, and not to the template itself, in case the template is made public:

1. On Deploy a Pod: Choose `H100 XSM` and click `Edit Template`
2. Select your GPU count
3. Click `Edit`
4. Click `Environment Variables`
5. Click `+ Add Environment Variable`
6. Click Lock to select secret
7. Click `hf_token` as value
8. Type `hf_token` as key
9. Click `+ Add Environment Variable`
10. Click Lock to select secret
11. Click `hf_user` as value
12. Type `hf_user` as key
13. Click `Set Overrides`
14. Click `Deploy On-Demand`

### Connect to the Runpod template via SSH

On your Terminal, run the provided RunPod command to connect via SSH (without SCP & SFTP support), in the format:

```
ssh <CONNECTION_STRING>@ssh.runpod.io -i ~/.ssh/<PRIVATE_KEY_FILE>
```

### Clone `QwenLM/Qwen3-VL`, install the dependencies, and prepare the repository

Connected to the template, run:

```
cd /workspace && \
apt update && \
apt install -y nano && \
git clone https://github.com/QwenLM/Qwen3-VL.git && \
python3.11 -m venv qwen_env && \
source qwen_env/bin/activate && \
python -m pip install --upgrade pip && \
pip install torch==2.6.0 && \
pip install packaging wheel psutil && \
pip install flash_attn==2.7.4.post1 --no-build-isolation && \
pip install torchvision==0.21.0 deepspeed==0.17.1 triton==3.2.0 accelerate==1.7.0 torchcodec==0.2 peft==0.17.1 && \
rm -r Qwen3-VL/qwen-vl-finetune/demo/images
```

### Open another Terminal window (locally, keeping the other SSH session open), and send the dataset, `chat_template.jinja`, `push_to_hub.py` and patches to RunPod

From the root project directory (locally), run (replacing `<PORT>`, `<PRIVATE_KEY_FILE>` and `<IP>` with the values from 'SSH over exposed TCP' on RunPod):

```
scp -P <PORT> -i ~/.ssh/<PRIVATE_KEY_FILE> -r \
    computer/LLM/datasets/vla_sft_dataset/images \
    computer/LLM/datasets/vla_sft_dataset/output/image_per_turn.json \
    root@<IP>:/workspace/Qwen3-VL/qwen-vl-finetune/demo/
```

```
scp -P <PORT> -i ~/.ssh/<PRIVATE_KEY_FILE> -r \
    computer/LLM/push_to_hub.py \
    computer/LLM/chat_template.jinja \
    computer/LLM/Qwen3-VL.patch \
    root@<IP>:/workspace/Qwen3-VL/qwen-vl-finetune/
```

After this, go back to the other Terminal window

### SFT

To fine-tune the VLM, run:

```
cd Qwen3-VL/qwen-vl-finetune
```

```
for f in *.patch; do patch -p0 < "$f"; done
```

Replace:

```
role = "user" if turn["from"] == "human" else "assistant"
...
if role == "user":
```

with:

```
role = "input" if turn["from"] == "input" else "output"
...
if role == "input":
```

And then replace `assistant`'s id with `output`'s id:

```
if input_ids_flat[pos] == 77091:
```

with:

```
if input_ids_flat[pos] == 32222:
```

Open `/workspace/Qwen3-VL/qwen-vl-finetune/qwenvl/train_qwen.py`:

```
cd ../train
nano train_qwen.py
```

Add:

```
try:
    print("Loading custom chat template from 'chat_template.jinja'")
    with open("chat_template.jinja", "r") as f:
        custom_chat_template = f.read()
    processor.chat_template = custom_chat_template
    processor.tokenizer.chat_template = custom_chat_template
    print("Successfully replaced default chat template with custom template.")
except Exception as e:
    print(f"ERROR: Failed to load custom chat template: {e}")
    sys.exit(1)
```

between:

```
processor = AutoProcessor.from_pretrained(
    model_args.model_name_or_path,
)
```

and:

```
if data_args.data_flatten or data_args.data_packing:
```

Create the fine-tuning script (`sft.sh`):

```
cd ../..
nano sft.sh
```

Paste it:

```
#!/bin/bash

MASTER_ADDR="127.0.0.1"
MASTER_PORT=$(shuf -i 20000-29999 -n 1)
NPROC_PER_NODE=1
MODEL_PATH="Qwen/Qwen2.5-VL-7B-Instruct"
OUTPUT_DIR="./checkpoints"
CACHE_DIR="./cache"
DATASETS="vla_sft"

torchrun --nproc_per_node=$NPROC_PER_NODE \
         --master_addr=$MASTER_ADDR \
         --master_port=$MASTER_PORT \
         qwenvl/train/train_qwen.py \
         --model_name_or_path $MODEL_PATH \
         --tune_mm_llm True \
         --tune_mm_vision False \
         --tune_mm_mlp False \
         --dataset_use $DATASETS \
         --output_dir $OUTPUT_DIR \
         --cache_dir $CACHE_DIR \
         --bf16 \
         --per_device_train_batch_size 1 \
         --gradient_accumulation_steps 1 \
         --learning_rate 1e-5 \
         --mm_projector_lr 1e-5 \
         --vision_tower_lr 1e-6 \
         --optim adamw_torch \
         --model_max_length 32768 \
         --data_flatten True \
         --data_packing True \
         --max_pixels 307328 \
         --min_pixels 306544 \
         --num_train_epochs 10 \
         --warmup_ratio 0.03 \
         --lr_scheduler_type "cosine" \
         --weight_decay 0.01 \
         --logging_steps 10 \
         --save_steps 200 \
         --save_total_limit 3 \
         --lora_enable True \
         --lora_r 64 \
         --lora_alpha 64
```

Save (e.g., `control + x`, `y`, `enter`)

Make the script executable:

```
chmod +x sft.sh
```

And run:

```
./sft.sh
```

### Push to Hub

Set the base model to `Qwen/Qwen2.5-VL-7B-Instruct` in `/workspace/Qwen3-VL/qwen-vl-finetune/checkpoints/README.md`:

```
cd checkpoints
nano README.md
```

Then save (e.g., `control + x`, `y`, `enter`)

Run:

```
cd ..
python push_to_hub.py
```

## Full Robot Execution

`https://console.runpod.io/hub/runpod-workers/worker-vllm`

https://github.com/runpod-workers/worker-vllm/blob/main/docs/configuration.md

To run the robot:

```
python production.py
```
