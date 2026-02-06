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
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("❌ Error: GROQ_API_KEY not found in environment variables.")
    print("Please create a .env file with your API key:")
    print("GROQ_API_KEY=your_api_key_here")
    sys.exit(1)

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
    
    def cancel(self):
        """Cancel recording without saving."""
        with self.lock:
            if not self.recording:
                return False
            self.recording = False
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        self.audio_data = []
        return True

# ============================================================================
# Audio Ducking (Mute Other Apps)
# ============================================================================

class AudioDucker:
    """Mute other applications during recording using PulseAudio/PipeWire."""
    
    def __init__(self):
        self.available = self._check_availability()
        self.muted_sinks = []
        self.original_volumes = {}
    
    def _check_availability(self):
        """Check if pactl is available."""
        try:
            result = subprocess.run(
                ["pactl", "--version"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except:
            return False
    
    def _get_sink_inputs(self):
        """Get list of active audio sink inputs (playing applications)."""
        if not self.available:
            return []
        
        try:
            result = subprocess.run(
                ["pactl", "list", "sink-inputs", "short"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                # Parse output: each line is "ID SINK ..."
                sink_inputs = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split()
                        if parts:
                            sink_inputs.append(parts[0])
                return sink_inputs
        except:
            pass
        return []
    
    def mute_others(self):
        """Mute all active audio sink inputs."""
        if not self.available:
            return
        
        self.muted_sinks = self._get_sink_inputs()
        
        for sink_id in self.muted_sinks:
            try:
                # Mute the sink input
                subprocess.run(
                    ["pactl", "set-sink-input-mute", sink_id, "1"],
                    capture_output=True,
                    timeout=1
                )
            except:
                pass
    
    def restore(self):
        """Unmute previously muted sink inputs."""
        if not self.available:
            return
        
        for sink_id in self.muted_sinks:
            try:
                # Unmute the sink input
                subprocess.run(
                    ["pactl", "set-sink-input-mute", sink_id, "0"],
                    capture_output=True,
                    timeout=1
                )
            except:
                pass
        
        self.muted_sinks = []
        self.original_volumes = {}

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
    def __init__(self, toggle_callback, cancel_callback=None):
        self.toggle_callback = toggle_callback
        self.cancel_callback = cancel_callback
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
                    self.toggle_callback()
                elif keysym == XK.XK_Escape and self.cancel_callback:
                    self.cancel_callback()
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
        self.ducker = AudioDucker()
        self.hotkey = HotkeyListener(self.toggle, self.cancel) if HAS_XLIB else None
        self.file_watcher = FileWatcher(self.toggle)
    
    def toggle(self):
        if not self.recorder.is_recording:
            if self.recorder.start():
                # Mute other applications
                self.ducker.mute_others()
                print("🎙️ Recording started")
                notify("🎙️ Recording started", "Glaido")
        else:
            duration = self.recorder.stop()
            # Restore audio regardless of recording success
            self.ducker.restore()
            
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
    
    def cancel(self):
        """Cancel recording without transcribing."""
        if self.recorder.is_recording:
            if self.recorder.cancel():
                # Restore audio
                self.ducker.restore()
                print("🚫 Recording cancelled")
                notify("🚫 Recording cancelled", "Glaido")
    
    def run(self):
        print("=" * 50)
        print("🎤 Glaido - Voice Transcription")
        print("=" * 50)
        print("Hotkey: Ctrl+Shift+Space (toggle)")
        print("Cancel: Escape (while recording)")
        print("Running in background...")
        print("Press Ctrl+C to exit")
        print("=" * 50)
        
        notify("✅ Glaido is ready!\nPress Ctrl+Shift+Space to record\nPress Escape to cancel", "Glaido")
        
        # Start watchers
        threading.Thread(target=self.file_watcher.start, daemon=True).start()
        
        try:
            if HAS_XLIB:
                # Run hotkey listener (blocks)
                self.hotkey.start()
            else:
                # Fallback: keep running
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")

def main():
    app = Glaido()
    app.run()

if __name__ == "__main__":
    main()
