import os
from datetime import datetime
from huggingface_hub import create_repo, upload_folder

#################
# Configuration #
#################

# Original (VLM) path
REGULAR_MODEL_PATH = "Qwen/Qwen3-VL-2B-Instruct"

timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
hf_user = os.environ.get("hf_user")
hf_token = os.environ.get("hf_token")
checkpoint_dir = f"./checkpoints"

def push_to_hub():
    try:
        print(f"push_to_hub: uploading {checkpoint_dir} to {hub_repo_id}...")
        upload_folder(
        repo_id=hub_repo_id,
        folder_path=checkpoint_dir,
        commit_message=f"checkpoints",
        token=hf_token,
        repo_type="model",
        )
        print("push_to_hub: successfully pushed model to the Hub")
        return True
    except Exception as e:
        print(f"push_to_hub: failed to push to Hub: {e}")
        return False

if not hf_user or not hf_token:
    raise RuntimeError("hf_user and hf_token environment variables must be set")

# SFTed (VLA) path
hub_repo_id = f"{hf_user}/{REGULAR_MODEL_PATH.split('/')[-1]}-VLA-{timestamp}"

create_repo(repo_id=hub_repo_id, exist_ok=True, token=hf_token, repo_type="model")
push_to_hub()