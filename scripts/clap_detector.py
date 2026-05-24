#!/usr/bin/env python3
"""
J.A.R.V.I.S. Background Clap & Voice Assistant.
Listens for a physical clap to wake up, responds, records the vocal task,
transcribes it via SpeechRecognition, queries the active ReAct agent, and speaks the reply back.
"""

import sys
import os
import time
import subprocess
import threading
import wave
import numpy as np
import sounddevice as sd
import speech_recognition as sr

# Configuration parameters
SAMPLE_RATE = 16000     # Recommended rate for speech recognition
BLOCK_SIZE = 1024        # Processing chunks
THRESHOLD_RATIO = 8.0   # Spike multiplier over ambient background
COOLDOWN_SECONDS = 3.0  # Cooldown between voice cycles

# Global Threading / State Coordinates
wake_event = threading.Event()
is_processing = False
is_warming_up = True
ambient_energy = 0.05
last_trigger_time = 0.0


def audio_callback(indata, frames, time_info, status):
    """Callback processed for each incoming audio buffer chunk when active."""
    global ambient_energy, last_trigger_time, is_processing, is_warming_up
    
    if status:
        print(f"[Audio Status Warning]: {status}", file=sys.stderr)
        
    # Calculate root-mean-square energy of the chunk
    energy = np.sqrt(np.mean(indata**2))
    
    # Smoothly update rolling ambient noise level (leak integration)
    ambient_energy = 0.98 * ambient_energy + 0.02 * max(energy, 0.001)

    if is_processing or is_warming_up:
        return
        
    current_time = time.time()
    
    # Check if peak energy is a sharp spike compared to rolling ambient noise
    if energy > THRESHOLD_RATIO * ambient_energy:
        if current_time - last_trigger_time > COOLDOWN_SECONDS:
            last_trigger_time = current_time
            wake_event.set()


def speak(text):
    """Vocalize response out loud using native macOS speech engine."""
    clean_text = text.replace("*", "").replace("_", "").replace("`", "").strip()
    if not clean_text:
        return
    subprocess.run(["say", "-v", "Daniel", clean_text])


def record_audio(duration=5):
    """Record microphone stream asynchronously for the full duration to prevent clicks and pops."""
    print("\n[J.A.R.V.I.S. Communicator]: Active. Speak your command...")
    
    # Start asynchronous recording of the full duration
    audio_data = sd.rec(int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='int16')
    
    # Draw progress bar while it records in the background
    chunk_duration = 0.5
    chunks = int(duration / chunk_duration)
    for i in range(chunks):
        time.sleep(chunk_duration)
        pct = int(((i + 1) / chunks) * 20)
        bar = "=" * pct + " " * (20 - pct)
        remaining = max(0.0, duration - (i + 1) * chunk_duration)
        sys.stdout.write(f"\rListening: [{bar}] {int(remaining)}s ")
        sys.stdout.flush()
        
    sd.wait()  # Ensure recording is fully complete
    print("\rListening: [====================] Processing...     ")
    sys.stdout.flush()
    return audio_data


def transcribe_audio(audio_data):
    """Write audio to temporary wav file and query transcription api."""
    temp_wav = "jarvis_temp_voice.wav"
    with wave.open(temp_wav, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_data.tobytes())
        
    r = sr.Recognizer()
    text = ""
    try:
        with sr.AudioFile(temp_wav) as source:
            audio = r.record(source)
        text = r.recognize_google(audio)
    except Exception:
        pass
        
    if os.path.exists(temp_wav):
        try:
            os.remove(temp_wav)
        except OSError:
            pass
            
    return text.strip()


def main():
    global is_processing
    import signal
    
    def sigterm_handler(signum, frame):
        raise KeyboardInterrupt
        
    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)

    print("======================================================================")
    print("      J.A.R.V.I.S. ACTIVE MONITORING SYSTEM — VOICE ASSISTANT         ")
    print("======================================================================")
    print("Microphone online. Listening for physical clap commands...")
    print("Press CTRL+C to terminate the active monitoring loop.")
    print("----------------------------------------------------------------------")
    
    try:
        while True:
            # Set state for active background clap monitoring
            wake_event.clear()
            is_processing = False
            is_warming_up = True
            
            with sd.InputStream(
                channels=1,
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                callback=audio_callback
            ):
                # Sleep briefly to calibrate ambient noise levels & avoid echo feedback
                time.sleep(1.5)
                is_warming_up = False
                
                while not wake_event.is_set():
                    time.sleep(0.1)
                    
            # Wake triggered! Enter processing gate
            is_processing = True
            print("\n[J.A.R.V.I.S. Wake]: \"Hello boss, welcome back.\"")
            speak("Hello boss, welcome back.")
            
            # Record voice command (5 seconds)
            audio_data = record_audio(5)
            
            # Transcribe recorded command
            command = transcribe_audio(audio_data)
            
            if command:
                print(f"[Command Received]: \"{command}\"")
                print("[J.A.R.V.I.S.]: Consulting ReAct intelligence pool...")
                
                # Execute via NVIDIA NIM (cloud engine)
                import sys as _sys
                _sys.path.insert(0, "/Users/dhanush/Desktop/Jarvis/OpenJarvis/src")
                from openjarvis.nvidia_config import NVIDIA_API_KEY, NVIDIA_DEFAULT_MODEL

                sub_env = os.environ.copy()
                sub_env["NVIDIA_API_KEY"] = NVIDIA_API_KEY

                cmd = [
                    "uv", "run", "jarvis", "ask", command,
                    "--engine", "cloud",
                    "--model", NVIDIA_DEFAULT_MODEL,
                    "--max-tokens", "300",
                ]

                res = subprocess.run(
                    cmd,
                    cwd="/Users/dhanush/Desktop/Jarvis/OpenJarvis",
                    capture_output=True,
                    text=True,
                    env=sub_env,
                    timeout=30,
                )
                
                output = res.stdout.strip()
                
                # Parse standard ReAct banner output or clean out ASCII logo
                logo_marker = "Private AI on your machine"
                if logo_marker in output:
                    response_text = output.split(logo_marker)[-1].strip()
                else:
                    response_text = output
                    
                if not response_text:
                    response_text = "I apologize, sir. I encountered a pipeline processing error."
                    
                print(f"[J.A.R.V.I.S. Response]: \"{response_text}\"")
                speak(response_text)
            else:
                print("[J.A.R.V.I.S. Warning]: No clear command detected.")
                speak("I apologize, sir, I could not hear any command.")
                
            # Cooldown block before resuming physical clap trigger
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("\n[J.A.R.V.I.S. Alert]: Active monitoring loop terminated by user.")
    except Exception as e:
        print(f"\n[Error] Failed to initialize hardware or processing cycle: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
