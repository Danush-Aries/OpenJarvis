#!/usr/bin/env python3
"""
OpenJarvis Autonomous Self-Correction Loop.
Interceptors standard errors, calls the Nvidia NIM core, generates corrective patches,
applies them, and retries the command.
"""

import sys
import os
import subprocess
import time
import json
import traceback
from typing import Dict, Any, List

# Ensure we can import anthropic from virtual env
try:
    import anthropic
except ImportError:
    print("[Error] Anthropic SDK not found in current environment. Please install it first.")
    sys.exit(1)


def run_command(command: List[str]) -> subprocess.CompletedProcess:
    """Run shell command and collect execution traces."""
    print(f"\n[Jarvis Run] Executing command: {' '.join(command)}")
    return subprocess.run(command, capture_output=True, text=True)


def call_nvidia_nim_for_patch(
    failed_cmd: str,
    stdout: str,
    stderr: str,
    file_contents: str,
    filepath: str
) -> Dict[str, Any]:
    """Prompts the Nvidia NIM core via proxy to analyze the failure and output a JSON patch."""
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "http://127.0.0.1:8082")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "freecc")
    
    client = anthropic.Anthropic(base_url=base_url, api_key=api_key)
    
    prompt = f"""
    The following terminal command failed.
    Command: {failed_cmd}
    
    Standard Output:
    {stdout}
    
    Standard Error (Traceback):
    {stderr}
    
    Target File Path: {filepath}
    Original File Contents:
    ---
    {file_contents}
    ---
    
    As Jarvis, diagnose the error and provide a corrected version of the code that will fix this issue.
    Your output MUST be a valid JSON object with the following keys:
    - "diagnosis": "A concise explanation of why the code failed."
    - "corrected_code": "The complete replacement code for the file."
    
    Provide ONLY the raw JSON object, without markdown wraps.
    """
    
    print("[Jarvis thinking] Prompting Nvidia NIM for diagnostic patch...")
    
    # We use our patched streaming messages flow
    with client.messages.stream(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    ) as stream:
        stream.until_done()
        resp = stream.get_final_message()
    raw_text = ""
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            raw_text = block.text
            break
        elif hasattr(block, "text"):
            raw_text = block.text
            break
    raw_text = raw_text.strip()
    
    # Strip markdown code blocks if the model returned them
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    raw_text = raw_text.strip()
    
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        # Fallback heuristic parser
        print("[Warning] Failed to parse JSON response. Attempting heuristic recovery.")
        return {
            "diagnosis": "Heuristic analysis of the error traceback.",
            "corrected_code": raw_text
        }


def main():
    if len(sys.argv) < 3:
        print("Usage: self_correction.py <target_filepath> <command...>")
        print("Example: self_correction.py my_script.py python my_script.py")
        sys.exit(1)
        
    target_file = sys.argv[1]
    command = sys.argv[2:]
    
    if not os.path.exists(target_file):
        print(f"[Error] Target file does not exist: {target_file}")
        sys.exit(1)
        
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        print(f"\n=================== ATTEMPT {attempt}/{max_retries} ===================")
        result = run_command(command)
        
        if result.returncode == 0:
            print("[Jarvis Success] Command completed with exit code 0!")
            print(result.stdout)
            sys.exit(0)
            
        print(f"[Jarvis Diagnosis] Command failed with exit code: {result.returncode}")
        print(f"Stderr capture:\n{result.stderr}")
        
        # Read current contents of the target script
        with open(target_file, "r") as f:
            file_contents = f.read()
            
        # Call NIM for a correction patch
        patch_info = call_nvidia_nim_for_patch(
            failed_cmd=" ".join(command),
            stdout=result.stdout,
            stderr=result.stderr,
            file_contents=file_contents,
            filepath=target_file
        )
        
        print(f"\n[Jarvis Diagnosis]: {patch_info.get('diagnosis')}")
        
        corrected = patch_info.get("corrected_code")
        if corrected:
            print(f"[Jarvis Healing] Writing corrective code to: {target_file}")
            with open(target_file, "w") as f:
                f.write(corrected)
            time.sleep(1)
        else:
            print("[Jarvis Alert] No corrected code block was generated. Aborting auto-correction.")
            sys.exit(1)
            
    print("[Jarvis Failure] Max self-correction retries reached without zero-exit outcome.")
    sys.exit(1)


if __name__ == "__main__":
    main()
