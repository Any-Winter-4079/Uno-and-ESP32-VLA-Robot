# Notes on `computer/LLM/results/`:

This folder contains results from:

- `CoT_Dec_PAL_tester_v2.py` with early LLM prompting and tool use experiments results
- `CoT_Dec_PAL_tester_v3.py` with early LLM prompting and tool use experiments results
- `eval_on_benchmark.py`, with (robot-related, either as baseline or for the actual robot) benchmark experiments results:
  - with regular instruct model in regular assistant mode
  - with regular instruct model in robot mode
  - with robot-SFTed model in robot mode
- `eval_on_driving.py` with (robot-related, either as baseline or for the actual robot) driving experiments results:
  - with regular instruct model in robot mode
  - with robot-SFTed model in robot mode

`eval_on_benchmark.py` and `eval_on_driving.py` run the 3 and 2 model/mode combinations in 4 sizes, for a total of 12 and 8 configs:

- `Qwen/Qwen3-VL-2B-Instruct`
- `Qwen/Qwen3-VL-4B-Instruct`
- `Qwen/Qwen3-VL-8B-Instruct`
- `Qwen/Qwen3-VL-32B-Instruct`
