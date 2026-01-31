#!/usr/bin/env python3
"""
Glaido - Voice Transcription (Background Service)
Global hotkey: Ctrl+Shift+Space to start/stop recording
"""

import os
import sys
import threading
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io import wavfile
from groq import Groq

# Try to import X11 for hotkeys
try:
    from Xlib import X, XK
    from Xlib.display import Display
    from Xlib.ext import record
    from Xlib.protocol import rq
    HAS_XLIB = True
except ImportError:
    HAS_XLIB = False

# ============================================================================
# Configuration
# ============================================================================

GROQ_API_KEY = "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"
SAMPLE_RATE = 16000
CHANNELS = 1
TEMP_DIR = Path(tempfile.gettempdir())
AUDIO_FILE = TEMP_DIR / "glaido_recording.wav"
TOGGLE_FILE = Path("/tmp/glaido_toggle_signal")

# ============================================================================
# Audio Recording
# ============================================================================

class AudioRecorder:
    def __init__(self):
        self.recording = False
        self.audio_data = []
        self.stream = None
        self.lock = threading.Lock()
    
    def _audio_callback(self, indata, frames, time, status):
        if self.recording:
            self.audio_data.append(indata.copy())
    
    def start(self):
        with self.lock:
            if self.recording:
                return False
            self.recording = True
            self.audio_data = []
        
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype='int16',
            callback=self._audio_callback
        )
        self.stream.start()
        return True
    
    def stop(self):
        with self.lock:
            if not self.recording:
                return None
            self.recording = False
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        if not self.audio_data:
            return None
        
        audio_array = np.concatenate(self.audio_data, axis=0)
        wavfile.write(str(AUDIO_FILE), SAMPLE_RATE, audio_array)
        return len(audio_array) / SAMPLE_RATE
    
    @property
    def is_recording(self):
        return self.recording

# ============================================================================
# Transcription & Clipboard
# ============================================================================

def transcribe_audio():
    if not AUDIO_FILE.exists():
        return None
    try:
        client = Groq(api_key=GROQ_API_KEY)
        with open(AUDIO_FILE, "rb") as f:
            result = client.audio.transcriptions.create(
                file=(AUDIO_FILE.name, f.read()),
                model="whisper-large-v3",
                response_format="text"
            )
        return result.strip() if result else None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def copy_to_clipboard(text):
    try:
        subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE).communicate(text.encode('utf-8'))
        return True
    except:
        try:
            subprocess.Popen(["xsel", "--clipboard", "--input"], stdin=subprocess.PIPE).communicate(text.encode('utf-8'))
            return True
        except:
            return False

def notify(message, title="Glaido"):
    """Send desktop notification."""
    try:
        subprocess.run(["notify-send", title, message], check=False)
    except:
        pass

# ============================================================================
# X11 Hotkey & File Watcher
# ============================================================================

class HotkeyListener:
    def __init__(self, callback):
        self.callback = callback
        self.display = None
        self.ctrl_pressed = False
        self.shift_pressed = False
    
    def _handler(self, reply):
        data = reply.data
        while len(data):
            event, data = rq.EventField(None).parse_binary_value(data, self.display.display, None, None)
            
            if event.type == X.KeyPress:
                keysym = self.display.keycode_to_keysym(event.detail, 0)
                if keysym in (XK.XK_Control_L, XK.XK_Control_R):
                    self.ctrl_pressed = True
                elif keysym in (XK.XK_Shift_L, XK.XK_Shift_R):
                    self.shift_pressed = True
                elif keysym == XK.XK_space and self.ctrl_pressed and self.shift_pressed:
                    self.callback()
            elif event.type == X.KeyRelease:
                keysym = self.display.keycode_to_keysym(event.detail, 0)
                if keysym in (XK.XK_Control_L, XK.XK_Control_R):
                    self.ctrl_pressed = False
                elif keysym in (XK.XK_Shift_L, XK.XK_Shift_R):
                    self.shift_pressed = False
    
    def start(self):
        self.display = Display()
        ctx = self.display.record_create_context(0, [record.AllClients], [{
            'core_requests': (0, 0), 'core_replies': (0, 0),
            'ext_requests': (0, 0, 0, 0), 'ext_replies': (0, 0, 0, 0),
            'delivered_events': (0, 0), 'device_events': (X.KeyPress, X.KeyRelease),
            'errors': (0, 0), 'client_started': False, 'client_died': False,
        }])
        self.display.record_enable_context(ctx, self._handler)
        self.display.record_free_context(ctx)

class FileWatcher:
    def __init__(self, callback):
        self.callback = callback
        self.last_mtime = 0
        self.running = False
    
    def start(self):
        self.running = True
        while self.running:
            try:
                if TOGGLE_FILE.exists():
                    mtime = TOGGLE_FILE.stat().st_mtime
                    if mtime > self.last_mtime:
                        self.last_mtime = mtime
                        self.callback()
            except:
                pass
            time.sleep(0.1)

# ============================================================================
# Main Application
# ============================================================================

class Glaido:
    def __init__(self):
        self.recorder = AudioRecorder()
        self.hotkey = HotkeyListener(self.toggle) if HAS_XLIB else None
        self.file_watcher = FileWatcher(self.toggle)
    
    def toggle(self):
        if not self.recorder.is_recording:
            if self.recorder.start():
                print("🎙️ Recording started")
                notify("🎙️ Recording started", "Glaido")
        else:
            duration = self.recorder.stop()
            if duration:
                print(f"💾 Recorded {duration:.1f}s - Transcribing...")
                notify("🔄 Transcribing...", "Glaido")
                
                def transcribe_task():
                    text = transcribe_audio()
                    if text:
                        copy_to_clipboard(text)
                        print(f"✅ Copied: {text[:60]}...")
                        notify(f"✅ Copied to clipboard!\n\n{text[:100]}...", "Glaido")
                    else:
                        print("❌ Transcription failed")
                        notify("❌ Transcription failed", "Glaido")
                
                threading.Thread(target=transcribe_task, daemon=True).start()
    
    def run(self):
        print("=" * 50)
        print("🎤 Glaido - Voice Transcription")
        print("=" * 50)
        print("Hotkey: Ctrl+Shift+Space")
        print("Running in background...")
        print("Press Ctrl+C to exit")
        print("=" * 50)
        
        notify("✅ Glaido is ready!\nPress Ctrl+Shift+Space to record", "Glaido")
        
        # Start watchers
        threading.Thread(target=self.file_watcher.start, daemon=True).start()
        
        if HAS_XLIB:
            # Run hotkey listener (blocks)
            self.hotkey.start()
        else:
            # Fallback: keep running
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")

def main():
    app = Glaido()
    app.run()

if __name__ == "__main__":
    main()
