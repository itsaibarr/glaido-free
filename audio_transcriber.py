#!/usr/bin/env python3
"""
Audio Transcriber - Voice recording with Groq Whisper transcription.
Press Enter to start recording, Enter again to stop and transcribe.
"""

import os
import sys
import threading
import numpy as np
import sounddevice as sd
from scipy.io import wavfile
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Groq API Key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("❌ Error: GROQ_API_KEY not found in environment variables.")
    print("Please create a .env file with your API key:")
    print("GROQ_API_KEY=your_api_key_here")
    sys.exit(1)

# Audio settings
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1
OUTPUT_FILE = "test.wav"

# Recording state
recording = False
audio_data = []
stream = None


def audio_callback(indata, frames, time, status):
    """Callback for audio stream."""
    global audio_data
    if status:
        print(f"⚠️  {status}")
    if recording:
        audio_data.append(indata.copy())


def start_recording():
    """Start recording audio from microphone."""
    global recording, audio_data, stream
    
    if recording:
        return
    
    recording = True
    audio_data = []
    
    print("\n🎙️  Recording... (Press Enter to stop)")
    
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, 
        channels=CHANNELS, 
        dtype='int16', 
        callback=audio_callback
    )
    stream.start()


def stop_recording():
    """Stop recording and save to WAV file."""
    global recording, stream, audio_data
    
    if not recording:
        return False
    
    recording = False
    
    if stream:
        stream.stop()
        stream.close()
        stream = None
    
    if not audio_data:
        print("⚠️  No audio recorded.")
        return False
    
    # Concatenate all audio chunks
    audio_array = np.concatenate(audio_data, axis=0)
    
    # Save as WAV
    wavfile.write(OUTPUT_FILE, SAMPLE_RATE, audio_array)
    duration = len(audio_array) / SAMPLE_RATE
    print(f"💾 Saved to {OUTPUT_FILE} ({duration:.1f}s)")
    
    return True


def transcribe_audio():
    """Send audio to Groq Whisper for transcription."""
    if not os.path.exists(OUTPUT_FILE):
        print("❌ No audio file found.")
        return None
    
    print("🔄 Transcribing with Groq Whisper...")
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        with open(OUTPUT_FILE, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(OUTPUT_FILE, audio_file.read()),
                model="whisper-large-v3",
                response_format="text"
            )
        
        return transcription
    
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        return None


def main():
    """Main entry point - simple Enter key toggle."""
    print("=" * 50)
    print("🎤 Audio Transcriber")
    print("=" * 50)
    print("Press Enter to start recording")
    print("Press Enter again to stop and transcribe")
    print("Type 'q' + Enter to quit")
    print("=" * 50)
    
    global recording
    
    while True:
        try:
            user_input = input("\n⏸️  Ready. Press Enter to record: ")
            
            if user_input.lower() == 'q':
                print("👋 Goodbye!")
                break
            
            # Start recording
            start_recording()
            
            # Wait for Enter to stop
            input()
            
            # Stop and transcribe
            if stop_recording():
                transcription = transcribe_audio()
                if transcription:
                    print("\n" + "=" * 50)
                    print("📝 TRANSCRIPTION:")
                    print("=" * 50)
                    print(transcription)
                    print("=" * 50)
        
        except KeyboardInterrupt:
            if recording:
                stop_recording()
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            if recording:
                stop_recording()


if __name__ == "__main__":
    main()
