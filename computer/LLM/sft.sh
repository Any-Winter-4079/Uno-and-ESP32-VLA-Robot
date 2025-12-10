#!/bin/bash

MASTER_ADDR="127.0.0.1"
MASTER_PORT=$(shuf -i 20000-29999 -n 1)
NPROC_PER_NODE=1
MODEL_PATH="Qwen/Qwen3-VL-8B-Instruct"
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