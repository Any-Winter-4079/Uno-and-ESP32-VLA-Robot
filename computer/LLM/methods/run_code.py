import os
import tempfile
import subprocess

####################################
# Run code with subprocess timeout #
####################################
def run_code_with_subprocess_timeout(code, timeout=3):
    try:
        code_wrapper = f"""
import json
import math
import sys

{code}

try:
    result = main()
    print(json.dumps(result))
except Exception as e:
    print(f"Error in main(): {{str(e)}}", file=sys.stderr)
"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode='w+') as temp_script:
            temp_script_name = temp_script.name
            temp_script.write(code_wrapper)

        completed_process = subprocess.run(['python', temp_script_name], capture_output=True, text=True, timeout=timeout)
        stdout = completed_process.stdout.strip()
        stderr = completed_process.stderr.strip()

        if completed_process.returncode == 0:
            return {"stdout": stdout, "stderr": stderr if stderr else None}
        else:
            return {"stdout": stdout if stdout else None, "stderr": stderr}
    
    except subprocess.TimeoutExpired:
        return {"stdout": None, "stderr": f"Execution timeout (timeout={timeout} seconds). Please check your code or set a longer timeout argument if you need to."}
    except Exception as e:
        return {"stdout": None, "stderr": f"Subprocess runner failed: {str(e)}"}
    finally:
        if temp_script_name and os.path.exists(temp_script_name):
            os.remove(temp_script_name)

########
# Test #
########
def main():
    pass
    code_1 = """import math\n\ndef main():\n    # Pre-calculating based on the guess that denominator is 3^(1/2)\n    numerator = math.sqrt(171 - 45)\n    denominator = math.sqrt(3)\n    base = numerator / denominator\n    result = base ** math.e\n    return result\n"""
    timeout = 10
    print(run_code_with_subprocess_timeout(code_1, timeout=timeout))
    code_2 = """import math\n\ndef main():\n    # Pre-calculating based on the guess that denominator is 3^(1/2)\n    numerator = math.sqrt(171 - 45)\n    denominator = math.sqrt(3)\n    base = numerator / denominator\n    print(base)\n    raise ValueError("This is a deliberate test error.")\n"""
    print(run_code_with_subprocess_timeout(code_2, timeout=timeout))

if __name__ == "__main__":
    main()