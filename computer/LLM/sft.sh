#!/bin/bash

USE_DEEPSPEED=true

MASTER_ADDR="127.0.0.1"
MASTER_PORT=$(shuf -i 20000-29999 -n 1)
NPROC_PER_NODE=$(nvidia-smi --list-gpus | wc -l)
MODEL_PATH="Qwen/Qwen3-VL-2B-Instruct"
OUTPUT_DIR="./checkpoints"
CACHE_DIR="./cache"
DATASETS="vla_sft"
DEEPSPEED="zero3.json"

# About max_pixels, min_pixels
# Given (28x28) pixels -> 1 token
# (640x480)/(28x28) -> 391.836735 tokens (min_tokens 391 and max_tokens 392)
# 391 tokens x (28x28) pixels/token = 306544 pixels
# 392 tokens x (28x28) pixels/token = 307328 pixels

# About gradient_checkpointing, lora_enable
if [ "$USE_DEEPSPEED" = true ]; then
  DEEPSPEED_ARG="--deepspeed $DEEPSPEED"
else
  DEEPSPEED_ARG=""
fi

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
         --gradient_accumulation_steps 4 \
         --learning_rate 1e-5 \
         --mm_projector_lr 1e-5 \
         --vision_tower_lr 1e-6 \
         --optim adamw_torch \
         --model_max_length 16384 \
         --data_flatten True \
         --data_packing True \
         --max_pixels 307328 \
         --min_pixels 306544 \
         --num_train_epochs 20 \
         --gradient_checkpointing True \
         --warmup_ratio 0.03 \
         --lr_scheduler_type "cosine" \
         --weight_decay 0.01 \
         --logging_steps 10 \
         --save_steps 200 \
         --save_total_limit 3 \
         --lora_enable False \
         --lora_r 64 \
         --lora_alpha 64 \
         --lora_dropout 0.0 \
         $DEEPSPEED_ARG