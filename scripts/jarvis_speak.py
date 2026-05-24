#!/usr/bin/env python3
"""
OpenJarvis Voice Wrapper.
Runs standard queries and pipes the synthesized textual output to macOS's native
high-quality British 'Daniel' voice to speak out loud in real time!
"""

import sys
import os
import subprocess
import threading


def speak_text(text: str):
    """Call the native macOS 'say' command with the British 'Daniel' voice."""
    # Strip any markdown symbols like asterisks or hashtags to make the voice smooth
    clean_text = text.replace("*", "").replace("#", "").replace("[", "").replace("]", "").replace("-", " ")
    
    # Run the speak command
    subprocess.run(["say", "-v", "Daniel", clean_text])


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/jarvis_speak.py \"<your question here>\"")
        sys.exit(1)
        
    query = sys.argv[1]
    
    # Set the proxy environment variables
    os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:8082"
    os.environ["ANTHROPIC_API_KEY"] = "freecc"
    
    print(f"\n[J.A.R.V.I.S. listening]: \"{query}\"")
    print("----------------------------------------------------------------------")
    
    # Run OpenJarvis ask command
    cmd = ["uv", "run", "jarvis", "ask", query]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    output = result.stdout.strip()
    
    # Extract response by cleaning the openjarvis banner
    banner_marker = "Private AI on your machine"
    if banner_marker in output:
        parts = output.split(banner_marker)
        response_text = parts[-1].strip()
    else:
        response_text = output
        
    if not response_text:
        response_text = "I apologize, sir. I was unable to compile a proper response."
        
    # Print response
    print(response_text)
    print("----------------------------------------------------------------------")
    
    # Speak the response out loud in a separate thread so console stays responsive
    speak_thread = threading.Thread(target=speak_text, args=(response_text,))
    speak_thread.start()
    speak_thread.join()


if __name__ == "__main__":
    main()
