# Notes on the `computer/LLM/methods/` code:

## Computer Setup

- Create a `.env` file within `computer/LLM/methods/` and add your `JINA_API_KEY`:

```
JINA_API_KEY=xxxx
```

## Use Cases

`v2/` and `v3/` are not needed to run the robot, and belong to early LLM experiments:

- `v2/` is for `CoT_Dec_PAL_tester_v2.py` and contains:

  - `chain_of_thought.py`
  - `decider.py`
  - `declarative.py`
  - `program_aided_lm.py`

- `v3/`is for `CoT_Dec_PAL_tester_v3.py` and contains:

  - `chain_of_thought.py`
  - `decider.py`
  - `declarative.py`
  - `program_aided_lm.py`
  - `zero_shot.py`

The results can be seen in more detail [here](https://github.com/Any-Winter-4079/Prompting-Experiments-2024).

`browse.py` and `run_code.py` contain methods callable by the robot:

- `browse.py` exposes 3 functions:

  - `browse_web`, to return a list of (`url_source`, `title`, `description`) results to a query.
  - `open_url`, to fetch the first `MAX_CHUNK_CHARS` characters either from the url or from `browsing_cache.json`.
  - `get_next_chunk`, to fetch a chunk in a specific range of characters, either from the url or from `browsing_cache.json`.

- `run_code.py` exposes:
  - `run_code_with_subprocess_timeout`, which allows for the (quite unsafe) execution of Python code in a subprocess.
